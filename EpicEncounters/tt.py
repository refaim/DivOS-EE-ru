import argparse
import collections
import csv
import hashlib
import os
import re
import sys
import xml.etree.ElementTree

RU_LETTERS_LC = 'абвгдеёжзийклмнопрстуфхцчшщьыъэюя'
RU_LETTERS_SET = set(RU_LETTERS_LC) | set(RU_LETTERS_LC.upper())

FIELD_FILE = 'File'
FIELD_UUID = 'UUID'
FIELD_ENGLISH = 'English'
FIELD_RUSSIAN = 'Russian'


class StatsEntry(object):
    def __init__(self, uuid):
        self._uuid = uuid
        self._attributes = []

    def get_uuid(self):
        return self._uuid

    def get_attributes(self):
        return self._attributes

    def parse_attribute(self, s):
        n = len(self._attributes) + 1
        if 'ExtraProperties' in s:
            attribute = ExtraPropertiesEntryAttribute(s, n)
        else:
            attribute = GenericEntryAttribute(s, n)
        self._attributes.append(attribute)

    @staticmethod
    def from_string(s):
        match = re.match(r'new entry "(?P<uuid>[^"]+)"', s)
        return None if match is None else StatsEntry(match.groupdict()['uuid'])

    def __repr__(self):
        strings = [f'new entry "{self._uuid}"']
        for attribute in self._attributes:
            strings.append(str(attribute))
        return '\n'.join(strings)


class GenericEntryAttribute(object):
    def __init__(self, s, i):
        self._raw = s
        self._idx = i

    def __repr__(self):
        return self._raw

    def _get_name(self):
        return 'generic'

    def get_id(self):
        return f'{self._get_name()}{self._idx}'

    def get_translatable_strings(self):
        yield from []

    def translate_string(self, key, text):
        assert False


class ExtraPropertiesEntryAttribute(GenericEntryAttribute):
    def __init__(self, s, i):
        super(ExtraPropertiesEntryAttribute, self).__init__(s, i)

        self._props = re.match(r'^data "ExtraProperties" "(.+)"$', s).group(1).split(';')

        self._translatable_props = collections.OrderedDict()
        for i, prop in enumerate(self._props):
            if re.search(r'\S(:|,)\S', prop) is None:
                self._translatable_props[i] = prop

    def __repr__(self):
        props = []
        for i, prop in enumerate(self._props):
            props.append(self._translatable_props.get(i, prop))
        return 'data "ExtraProperties" "{}"'.format(';'.join(props))

    def _get_name(self):
        return 'ep'

    def get_translatable_strings(self):
        yield from self._translatable_props.items()

    def translate_string(self, key, text):
        assert key in self._translatable_props
        self._translatable_props[key] = text


def get_all_stats_entries(file_contents):
    cur_entry = None
    for line_number, line in get_stripped_significant_stats_lines(file_contents):
        new_entry = StatsEntry.from_string(line)
        if new_entry is not None:
            if cur_entry is not None:
                yield cur_entry
            cur_entry = new_entry
        else:
            cur_entry.parse_attribute(line)
    if cur_entry is not None:
        yield cur_entry


def get_stripped_significant_stats_lines(file_contents):
    for i, line in enumerate(file_contents.splitlines()):
        line = line.strip()
        if line and not line.startswith('//'):
            yield i + 1, line


def get_lsx_element_trees(directory):
    for file_path, file_name in get_files_by_extension(directory, 'lsx'):
        yield file_path, xml.etree.ElementTree.parse(file_path)


def get_translatable_nodes_attributes(element_tree):
    for node in element_tree.getroot().findall('./region/node/children/node'):
        pairs = []

        uuid_node = node.find('attribute[@id="UUID"]')
        if uuid_node is not None:
            pairs.append([uuid_node.attrib['value'], node.find('attribute[@id="Content"]')])
        else:
            name_node = node.find('attribute[@id="Name"]')
            for attr in ['DisplayName', 'Description']:
                text_node = node.find(f'attribute[@id="{attr}"]')
                if text_node is not None:
                    pairs.append([f'{name_node.attrib["value"]}_{attr}', text_node])

        for text_id, text_node in pairs:
            yield text_id, text_node, text_node.attrib['value']


def get_translatable_stats_files(directory):
    translatable_files = set((s.lower() for s in ['AMER_Uniques.txt', 'Armor.txt', 'BAAR_Potion.txt', 'BAAR_WeaponMods.txt', 'Potion.txt', 'Shield.txt', 'Weapon.txt']))
    for file_path, file_name in get_files_by_extension(directory, 'txt'):
        if file_name.lower() in translatable_files:
            with open(file_path, 'r', encoding='utf-8') as file_object:
                file_contents = file_object.read()
            yield file_path, file_contents


def make_stats_text_uuid(stats_entry, entry_attribute, attribute_text_id):
    return hashlib.sha1(';'.join([stats_entry.get_uuid(), entry_attribute.get_id(), str(attribute_text_id)]).encode('utf-8')).hexdigest()


def get_files_by_extension(directory, ext):
    def normalize_extension(s):
        return s.lstrip('.').lower()

    ext = normalize_extension(ext)
    # TODO sorted
    for file_name in os.listdir(directory):
        if normalize_extension(os.path.splitext(file_name)[1]) == ext:
            file_path = os.path.join(directory, file_name)
            yield file_path, file_name


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['game_to_text', 'text_to_game'])
    parser.add_argument('src', help='path to mod directory with Data folder for game_to_text, path to csv for text_to_game')
    parser.add_argument('dst', help='path to csv for game_to_text, path to mod directory with Data folder for text_to_game')
    args = parser.parse_args()

    if args.mode == 'game_to_text':
        assert os.path.isdir(args.src)
        assert not os.path.exists(args.dst) or os.path.isfile(args.dst)
        csv_file_path = args.dst
        mod_directory_path = args.src
    else:
        assert os.path.isfile(args.src)
        assert os.path.isdir(args.dst)
        csv_file_path = args.src
        mod_directory_path = args.dst

    lsx_directory_paths = [
        ('Ln', os.path.join(mod_directory_path, 'Data', 'Mods', 'Epic_Encounters_071a986c-9bfa-425e-ac72-7e26177c08f6', 'Localization')),
        ('Rt', os.path.join(mod_directory_path, 'Data', 'Public', 'Epic_Encounters_071a986c-9bfa-425e-ac72-7e26177c08f6', 'RootTemplates')),
    ]

    stats_txt_directory_path = os.path.join(mod_directory_path, 'Data', 'Public', 'Epic_Encounters_071a986c-9bfa-425e-ac72-7e26177c08f6', 'Stats', 'Generated', 'Data')
    assert os.path.isdir(stats_txt_directory_path)

    def get_file_key(file_path, directory_code):
        return f'{directory_code}\\{os.path.basename(file_path)}'

    csv_strings_ru = {}
    csv_strings_en = {}
    if os.path.exists(csv_file_path):
        with open(csv_file_path, 'r', encoding='utf-8-sig') as csv_file_object:
            for csv_row in csv.DictReader(csv_file_object, delimiter=';'):
                for text_source_field, dictionary in {FIELD_ENGLISH: csv_strings_en, FIELD_RUSSIAN: csv_strings_ru}.items():
                    if csv_row[text_source_field]:
                        dictionary.setdefault(csv_row[FIELD_FILE], {})[csv_row[FIELD_UUID]] = csv_row[text_source_field]

    if args.mode == 'game_to_text':

        with open(csv_file_path, 'w', encoding='utf-8-sig', newline='\n') as csv_file_object:
            csv_writer = csv.DictWriter(csv_file_object, [FIELD_FILE, FIELD_UUID, FIELD_ENGLISH, FIELD_RUSSIAN], delimiter=';', lineterminator='\n')
            csv_writer.writeheader()

            def get_both_lang_texts(file_path, directory_code, text_id, text):
                if set(text) & RU_LETTERS_SET:
                    english_text, russian_text = csv_strings_en.get(get_file_key(file_path, directory_code), {}).get(text_id), text
                else:
                    english_text, russian_text = text, csv_strings_ru.get(get_file_key(file_path, directory_code), {}).get(text_id)
                return english_text, russian_text

            for directory_code, lsx_directory_path in lsx_directory_paths:
                for file_path, element_tree in get_lsx_element_trees(lsx_directory_path):
                    for text_id, text_node, text_value in get_translatable_nodes_attributes(element_tree):
                        english_text, russian_text = get_both_lang_texts(file_path, directory_code, text_id, text_value)
                        csv_writer.writerow({FIELD_FILE: get_file_key(file_path, directory_code), FIELD_UUID: text_id, FIELD_ENGLISH: english_text, FIELD_RUSSIAN: russian_text})

            for file_path, file_contents in get_translatable_stats_files(stats_txt_directory_path):
                for entry in get_all_stats_entries(file_contents):
                    for attribute in entry.get_attributes():
                        for attribute_text_id, text in attribute.get_translatable_strings():
                            file_text_uuid = make_stats_text_uuid(entry, attribute, attribute_text_id)
                            english_text, russian_text = get_both_lang_texts(file_path, 'St', file_text_uuid, text)
                            csv_writer.writerow({FIELD_FILE: get_file_key(file_path, 'St'), FIELD_UUID: file_text_uuid, FIELD_ENGLISH: english_text, FIELD_RUSSIAN: russian_text})

    else:

        for directory_code, lsx_directory_path in lsx_directory_paths:
            for file_path, element_tree in get_lsx_element_trees(lsx_directory_path):
                for text_id, text_node, text_value in get_translatable_nodes_attributes(element_tree):
                    text_node.set('value', csv_strings_ru.get(get_file_key(file_path, directory_code), {}).get(text_id, text_value))
                element_tree.write(file_path, encoding='utf-8', xml_declaration=True)

        for file_path, file_contents in get_translatable_stats_files(stats_txt_directory_path):
            entry_strings = []
            for entry in get_all_stats_entries(file_contents):
                for attribute in entry.get_attributes():
                    for attribute_text_id, text in attribute.get_translatable_strings():
                        file_text_uuid = make_stats_text_uuid(entry, attribute, attribute_text_id)
                        attribute.translate_string(attribute_text_id, csv_strings_ru.get(get_file_key(file_path, 'St'), {}).get(file_text_uuid, text))
                entry_strings.append(str(entry))

            with open(file_path, 'w', encoding='utf-8', newline='\n') as file_object:
                file_object.write('\n\n'.join(entry_strings))

    return 0


if __name__ == '__main__':
    sys.exit(main())
