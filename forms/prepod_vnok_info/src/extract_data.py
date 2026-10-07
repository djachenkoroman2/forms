#!/usr/bin/env python3
"""Extract the saved XFA datasets from a PDF as UTF-8 JSON, without OCR."""
import argparse
import json
from pathlib import Path
import sys

from defusedxml import ElementTree as ET
from pypdf import PdfReader
from pypdf.generic import ArrayObject

DATA_NS = 'http://www.xfa.org/schema/xfa-data/1.0/'
DAYS = ('monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday')
STUDENT_FIELDS = ('id', 'full_name', 'group_code', 'phone', 'email', 'task',
                  'expected_results', 'status', 'notes')


def child(parent, name):
    if parent is None:
        return None
    matches = parent.findall(name)
    if len(matches) > 1:
        raise ValueError(f'Повторяется одиночное поле: {name}')
    return matches[0] if matches else None


def value(parent, name):
    node = child(parent, name)
    if node is None:
        return ''
    if len(node):
        raise ValueError(f'Вместо текста обнаружена вложенная структура: {name}')
    return node.text or ''


def rows(parent, container, item):
    node = child(parent, container)
    return [] if node is None else node.findall(item)


def parse_datasets(xml):
    """Accept a datasets packet or a complete XDP stream; reject unsafe XML."""
    tree = ET.fromstring(xml, forbid_dtd=True)
    tag = f'{{{DATA_NS}}}datasets'
    packets = [tree] if tree.tag == tag else tree.findall(tag)
    if len(packets) != 1:
        raise ValueError('Ожидался ровно один пакет XFA datasets.')
    roots = packets[0].findall(f'{{{DATA_NS}}}data/formData')
    if len(roots) != 1:
        raise ValueError('Не найден однозначный объект formData.')
    root = roots[0]
    data = {key: value(root, key) for key in ('schema_version', 'form_id')}
    if data != {'schema_version': '1.0', 'form_id': 'prepod_vnok_info'}:
        raise ValueError('Неподдерживаемый идентификатор формы или версия схемы.')
    teacher = child(root, 'teacher')
    data['teacher'] = {key: value(teacher, key) for key in ('full_name', 'position')}
    data['students'] = []
    ids = set()

    def check_id(record):
        identifier = record['id']
        if not identifier.strip() or identifier in ids:
            raise ValueError(f'Пустой или повторяющийся идентификатор записи: {identifier!r}')
        ids.add(identifier)

    for node in rows(root, 'students', 'student'):
        student = {key: value(node, key) for key in STUDENT_FIELDS}
        check_id(student)
        student['schedule'] = []
        for entry in rows(node, 'schedule', 'entry'):
            row = {key: value(entry, key) for key in ('id', 'mode', 'time_from', 'time_to', 'room')}
            check_id(row)
            weekdays = child(entry, 'weekdays')
            row['weekdays'] = []
            for day in DAYS:
                state = value(weekdays, day)
                if state not in ('', '0', '1'):
                    raise ValueError(f'Некорректное значение дня недели: {day}={state!r}')
                if state == '1':
                    row['weekdays'].append(day)
            student['schedule'].append(row)
        student['achievements'] = []
        for entry in rows(node, 'achievements', 'achievement'):
            row = {key: value(entry, key) for key in ('id', 'text')}
            check_id(row)
            student['achievements'].append(row)
        data['students'].append(student)
    return data


def extract_data(path):
    reader = PdfReader(path)
    acroform = reader.trailer['/Root'].get('/AcroForm')
    if acroform is None:
        raise ValueError('В PDF нет интерактивной XFA-формы (возможно, он получен печатью).')
    xfa = acroform.get_object().get('/XFA')
    if xfa is None:
        raise ValueError('В PDF отсутствуют данные XFA.')
    xfa = xfa.get_object()
    if isinstance(xfa, ArrayObject):
        if len(xfa) % 2:
            raise ValueError('Повреждён список пакетов XFA.')
        packets = [xfa[i + 1].get_object() for i in range(0, len(xfa), 2)
                   if str(xfa[i]) == 'datasets']
        if len(packets) != 1:
            raise ValueError('Ожидался ровно один пакет datasets в PDF.')
        return parse_datasets(packets[0].get_data())
    if not hasattr(xfa, 'get_data'):
        raise ValueError('Неподдерживаемое представление XFA.')
    return parse_datasets(xfa.get_data())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pdf', type=Path)
    parser.add_argument('--output', type=Path, help='Новый JSON-файл; существующие файлы не перезаписываются.')
    args = parser.parse_args()
    try:
        result = json.dumps(extract_data(args.pdf), ensure_ascii=False, indent=2) + '\n'
        if args.output:
            with args.output.open('x', encoding='utf-8') as output:
                output.write(result)
        else:
            sys.stdout.write(result)
    except Exception as error:
        parser.exit(1, f'Ошибка извлечения: {error}\n')


if __name__ == '__main__':
    main()
