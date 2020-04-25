import argparse
import csv
import os
import sys
import xml.etree.ElementTree

RU_LETTERS_LC = 'абвгдеёжзийклмнопрстуфхцчшщьыъэюя'
RU_LETTERS_SET = set(RU_LETTERS_LC) | set(RU_LETTERS_LC.upper())

FIELD_FILE = 'File'
FIELD_UUID = 'UUID'
FIELD_ENGLISH = 'English'
FIELD_RUSSIAN = 'Russian'


def get_lsx_element_trees(directory):
    for file_name in os.listdir(directory):
        if os.path.splitext(file_name)[1] == '.lsx':
            file_path = os.path.join(directory, file_name)
            yield file_path, file_name, xml.etree.ElementTree.parse(file_path)


def get_translatable_nodes_attributes(element_tree):
    for node in element_tree.getroot().findall('./region/node/children/node'):
        uuid_node = node.find('attribute[@id="UUID"]')
        text_node = node.find('attribute[@id="Content"]')
        yield uuid_node, uuid_node.attrib['value'], text_node, text_node.attrib['value']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['game_to_text', 'text_to_game'])
    parser.add_argument('src', help='path to directory for game_to_text, path to csv for text_to_game')
    parser.add_argument('dst', help='path to csv for game_to_text, path to directory for text_to_game')
    args = parser.parse_args()

    if args.mode == 'game_to_text':
        assert os.path.isdir(args.src)
        assert not os.path.exists(args.dst) or os.path.isfile(args.dst)
        csv_file_path = args.dst
        lsx_directory_path = args.src
    else:
        assert os.path.isfile(args.src)
        assert os.path.isdir(args.dst)
        csv_file_path = args.src
        lsx_directory_path = args.dst

    csv_strings_ru = {}
    csv_strings_en = {}
    if os.path.exists(csv_file_path):
        with open(csv_file_path, 'r', encoding='utf-8-sig') as csv_file_object:
            for csv_row in csv.DictReader(csv_file_object, delimiter=';'):
                for text_source_field, dictionary in {FIELD_ENGLISH: csv_strings_en, FIELD_RUSSIAN: csv_strings_ru}.items():
                    dictionary.setdefault(csv_row[FIELD_FILE], {})[csv_row[FIELD_UUID]] = csv_row[text_source_field]

    if args.mode == 'game_to_text':
        with open(csv_file_path, 'w', encoding='utf-8-sig', newline='\n') as csv_file_object:
            csv_writer = csv.DictWriter(csv_file_object, [FIELD_FILE, FIELD_UUID, FIELD_ENGLISH, FIELD_RUSSIAN], delimiter=';', lineterminator='\n')
            csv_writer.writeheader()

            for file_path, file_name, tree in get_lsx_element_trees(lsx_directory_path):
                for uuid_node, uuid_value, text_node, text_value in get_translatable_nodes_attributes(tree):
                    if set(text_value) & RU_LETTERS_SET:
                        english_text, russian_text = csv_strings_en.get(file_name, {}).get(uuid_value), text_value
                    else:
                        english_text, russian_text = text_value, csv_strings_ru.get(file_name, {}).get(uuid_value)
                    csv_writer.writerow({FIELD_FILE: file_name, FIELD_UUID: uuid_value, FIELD_ENGLISH: english_text, FIELD_RUSSIAN: russian_text})
    else:
        for file_path, file_name, tree in get_lsx_element_trees(lsx_directory_path):
            for uuid_node, uuid_value, text_node, text_value in get_translatable_nodes_attributes(tree):
                text_node.set('value', csv_strings_ru.get(file_name, {}).get(uuid_value, text_value))
            tree.write(file_path, encoding='utf-8-sig')

    return 0


if __name__ == '__main__':
    sys.exit(main())
