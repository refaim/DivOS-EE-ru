import argparse
import csv
import os
import sys
import xml.etree.ElementTree

RU_LC = 'абвгдеёжзийклмнопрстуфхцчшщьыъэюя'

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('source_directory')
    parser.add_argument('destination_file')
    args = parser.parse_args()

    russian_letters = set(RU_LC) | set(RU_LC.upper())

    with open(args.destination_file, 'w', encoding='utf-8-sig', newline='\n') as csv_file_object:
        csv_writer = csv.writer(csv_file_object, delimiter=';')
        csv_writer.writerow(['File', 'UUID', 'English', 'Russian'])

        for file_name in os.listdir(args.source_directory):
            if os.path.splitext(file_name)[1] == '.lsx':
                tree = xml.etree.ElementTree.parse(os.path.join(args.source_directory, file_name))
                for node in tree.getroot().findall('./region/node/children/node'):
                    uuid = node.find('attribute[@id="UUID"]').attrib['value']
                    text = node.find('attribute[@id="Content"]').attrib['value']

                    if set(text) & russian_letters:
                        english_text, russian_text = None, text
                    else:
                        english_text, russian_text = text, None

                    csv_writer.writerow([file_name, uuid, english_text, russian_text])

    return 0

if __name__ == '__main__':
    sys.exit(main())
