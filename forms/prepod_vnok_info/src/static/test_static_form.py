"""Checks of the static one-student AcroForm. A real viewer is checked separately (firefox_check.py)."""
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, TextStringObject

from acroform import FF_MULTILINE, FF_READ_ONLY, FF_REQUIRED, field_type, iter_terminal_fields, set_values
from build_static_form import (ACHIEVEMENT_ROWS, DATE_FORMAT, FIELD_W, FIELD_X, FONT, LABEL_W, LEFT, RIGHT, SCHEDULE_MIN_H,
                               TITLE, WIDTH, build_pdf)
from extract_static import check, extract_data
from prepare_copy import prepare_copy

DOCS = Path(__file__).resolve().parents[2] / 'docs'
DRAFTS = Path(__file__).resolve().parents[2] / 'output' / 'drafts'
STUDENT_KEYS = ('last_name', 'first_name', 'middle_name', 'course', 'group_code', 'phone', 'email', 'task',
                'schedule', 'expected_results', 'status', 'notes')


def values_from(data):
    """Flatten schema-2.0 JSON with one student into field values."""
    student = data['students'][0]
    values = {'meta.date_filled': data['date_filled']}
    values.update({'teacher.' + k: v for k, v in data['teacher'].items()})
    values.update({'student.' + k: student[k] for k in STUDENT_KEYS})
    for item in student['achievements']:
        values[f"achievements.{item['id'].split('-')[-1]}.text"] = item['text']
    return values


class StaticFormTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)
        self.blank = build_pdf(self.dir / 'blank.pdf')

    def fields(self, path):
        return dict(iter_terminal_fields(PdfReader(path).trailer['/Root']['/AcroForm']['/Fields']))

    def fill(self, source, values, name):
        writer = PdfWriter(clone_from=PdfReader(source))
        set_values(writer, values)
        target = self.dir / name
        writer.write(target)
        return target

    def test_no_xfa_buttons_and_only_date_scripts(self):
        reader = PdfReader(self.blank)
        root = reader.trailer['/Root']
        self.assertNotIn('/XFA', root['/AcroForm'])
        for key in ('/NeedsRendering', '/OpenAction', '/Names', '/AA'):
            self.assertNotIn(key, root)
        for page in reader.pages:
            self.assertNotIn('/AA', page)
        raw = self.blank.read_bytes()
        for marker in (b'/SubmitForm', b'/Launch', b'/Perms', b'/Encrypt'):
            self.assertNotIn(marker, raw)
        fields = self.fields(self.blank)
        self.assertTrue(all(field_type(f) == '/Tx' for f in fields.values()))
        # The only scripts: the standard date format/keystroke actions of the date field.
        with_actions = {name: f['/AA'] for name, f in fields.items() if '/AA' in f}
        self.assertEqual(list(with_actions), ['meta.date_filled'])
        actions = with_actions['meta.date_filled']
        self.assertEqual(sorted(actions), ['/F', '/K'])
        self.assertEqual(actions['/F']['/S'], '/JavaScript')
        self.assertEqual(str(actions['/F']['/JS']), f'AFDate_FormatEx("{DATE_FORMAT}");')
        self.assertEqual(str(actions['/K']['/JS']), f'AFDate_KeystrokeEx("{DATE_FORMAT}");')
        self.assertEqual(DATE_FORMAT, 'dd.mm.yyyy')
        self.assertEqual(raw.count(b'/JavaScript'), 2)

    def test_title_and_pages(self):
        reader = PdfReader(self.blank)
        self.assertEqual(reader.metadata.title, TITLE)
        self.assertEqual(TITLE, 'Информация о студенте (курсанте)')
        self.assertEqual(len(reader.pages), 3)

    def test_liberation_serif_full_and_appearances(self):
        reader = PdfReader(self.blank)
        acroform = reader.trailer['/Root']['/AcroForm']
        self.assertEqual(list(acroform['/DR']['/Font']), ['/Serif'])
        font = acroform['/DR']['/Font']['/Serif']
        descriptor = font['/DescendantFonts'][0]['/FontDescriptor']
        self.assertEqual(descriptor['/FontName'], '/LiberationSerif')
        self.assertEqual(descriptor['/FontFile2'].get_data(), FONT.read_bytes(), 'field font must not be a subset')
        self.assertIn('/ToUnicode', font)
        for page in reader.pages:
            self.assertEqual(page['/Tabs'], '/R')
            bold = page['/Resources']['/Font']['/SerifBold']
            self.assertRegex(str(bold['/BaseFont']), r'^/[A-Z]{6}\+LiberationSerif-Bold$')
        for name, field in self.fields(self.blank).items():
            self.assertIn('/AP', field, name)
            self.assertIn('/Serif ', field['/DA'], name)

    def test_grid_30_70_and_no_overlap(self):
        self.assertAlmostEqual(LABEL_W / WIDTH, 0.30, places=3)
        self.assertAlmostEqual(FIELD_W / WIDTH, 0.70, places=3)
        for number, page in enumerate(PdfReader(self.blank).pages, 1):
            rects = []
            for annot in page['/Annots']:
                if int(annot.get_object()['/F']) & 2:      # hidden service fields are not part of the grid
                    continue
                x0, y0, x1, y1 = (float(v) for v in annot.get_object()['/Rect'])
                self.assertAlmostEqual(x0, FIELD_X, places=1)
                self.assertAlmostEqual(x1 - x0, FIELD_W, places=1)
                self.assertLessEqual(x1, RIGHT + 0.01)
                self.assertGreaterEqual(y0, 40)
                self.assertLessEqual(y1, 842 - 40)
                rects.append((y0, y1))
            rects.sort()
            for (_, top), (bottom, _) in zip(rects, rects[1:]):
                self.assertLessEqual(top, bottom, f'overlap on page {number}')
            # Labels stay in the left column: no page text starts inside the field column.
            starts = [float(x) for x in re.findall(rb'([\d.]+) [\d.]+ Td <', page.get_contents().get_data())]
            self.assertFalse([x for x in starts if FIELD_X - 8 < x < RIGHT], f'text in field column, page {number}')
            self.assertTrue(all(x >= LEFT for x in starts))

    def test_service_data_hidden(self):
        reader = PdfReader(self.blank)
        fields = self.fields(self.blank)
        service = {'meta.form_id', 'meta.schema_version', 'student.id'}
        for name, field in fields.items():
            flags = int(field['/F'])
            if name in service:
                self.assertEqual(flags, 2, name)        # Hidden, not Print
            else:
                self.assertEqual(flags, 4, name)        # Print, visible
        text = ''.join(page.extract_text() for page in reader.pages)
        self.assertNotIn('Служебные', text)
        self.assertNotIn('ID анкеты', text)
        self.assertEqual(sum(1 for f in fields.values() if not int(f['/F']) & 2), 26)

    def test_field_set_and_flags(self):
        fields = self.fields(self.blank)
        expected = ({'meta.date_filled', 'meta.form_id', 'meta.schema_version', 'student.id', 'student.notes'} |
                    {'teacher.' + k for k in ('full_name', 'position', 'department')} |
                    {'student.' + k for k in STUDENT_KEYS} |
                    {f'achievements.{i}.text' for i in range(1, ACHIEVEMENT_ROWS + 1)})
        self.assertEqual(set(fields), expected)
        required = {n for n, f in fields.items() if int(f.get('/Ff', 0)) & FF_REQUIRED}
        self.assertEqual(required, {'student.' + k for k in ('last_name', 'first_name', 'group_code', 'phone',
                                                             'email', 'task')})
        readonly = {n for n, f in fields.items() if int(f.get('/Ff', 0)) & FF_READ_ONLY}
        self.assertEqual(readonly, {'meta.form_id', 'meta.schema_version', 'student.id'})
        multiline = {n for n, f in fields.items() if int(f.get('/Ff', 0)) & FF_MULTILINE}
        self.assertEqual(multiline, {'student.task', 'student.schedule', 'student.expected_results', 'student.notes'} |
                         {f'achievements.{i}.text' for i in range(1, ACHIEVEMENT_ROWS + 1)})
        rect = [float(v) for v in fields['student.schedule']['/Rect']]
        self.assertGreaterEqual(rect[3] - rect[1], SCHEDULE_MIN_H)
        self.assertGreaterEqual(SCHEDULE_MIN_H, 8 * 11 * 1.15)
        for name, field in fields.items():
            label = str(field['/TU'])
            self.assertTrue(label and label != name, name)
            self.assertEqual(label.endswith(' *'), name in required, name)
        self.assertEqual(str(fields['meta.schema_version']['/V']), '2.0')

    def test_example_round_trip(self):
        data = json.loads((DOCS / 'example-data-v2.json').read_text(encoding='utf-8'))
        copy, _ = prepare_copy(self.blank, self.dir / 'copy.pdf', student_id=data['students'][0]['id'])
        filled = self.fill(copy, values_from(data), 'filled.pdf')
        self.assertEqual(extract_data(filled), data)
        self.assertEqual(check(data), ([], []))

    def test_blank_and_incomplete(self):
        with self.assertRaisesRegex(ValueError, 'ID анкеты не назначен'):
            extract_data(self.blank)
        data = extract_data(self.blank, assign_id=True)
        student = data['students'][0]
        self.assertTrue(student['id'].startswith('student-unassigned-'))
        self.assertEqual((student['schedule'], student['achievements'], data['date_filled']), ('', [], ''))
        errors, warnings = check(data)
        self.assertEqual(len(errors), 6)
        self.assertEqual(warnings, [])
        self.assertFalse(any('Отчество' in e or 'Курс' in e or 'Дата' in e for e in errors))

    def test_check_date_course_email(self):
        copy, _ = prepare_copy(self.blank, self.dir / 'copy.pdf')
        # Firefox (PDF.js) stores dates as YYYY-MM-DD; a valid one is normalized to ДД.ММ.ГГГГ.
        cases = {'31.02.2026': (True, '31.02.2026'), '2026-10-07': (False, '07.10.2026'),
                 '2026-02-31': (True, '2026-02-31'), '7.10.2026': (True, '7.10.2026'),
                 '07.10.2026': (False, '07.10.2026'), '': (False, '')}
        for index, (date, (bad, extracted)) in enumerate(cases.items()):
            filled = self.fill(copy, {'meta.date_filled': date}, f'date{index}.pdf')
            data = extract_data(filled)
            self.assertEqual(data['date_filled'], extracted, date)
            errors, _ = check(data)
            self.assertEqual(any(e.startswith('Дата заполнения') for e in errors), bad, date)
        for index, (course, bad) in enumerate({'0': True, '7': True, 'третий': True, '3': False, ' 6 ': False,
                                                '': False}.items()):
            filled = self.fill(copy, {'student.course': course}, f'course{index}.pdf')
            errors, warnings = check(extract_data(filled))
            self.assertEqual(bool(warnings), bad, course)
            self.assertFalse(any(e.startswith('Курс') for e in errors))
        filled = self.fill(copy, {'student.email': 'abc@'}, 'email.pdf')
        self.assertIn('Электронная почта: неверный формат адреса.', check(extract_data(filled))[0])

    def test_text_kept_verbatim(self):
        copy, _ = prepare_copy(self.blank, self.dir / 'copy.pdf')
        long_text = 'Длинный текст <задачи> & «детали» ёЁ №\n' * 1500
        filled = self.fill(copy, {'student.phone': '+00 001', 'student.group_code': '001-А', 'student.course': '03',
                                  'student.task': long_text, 'student.schedule': long_text,
                                  'meta.date_filled': ' 07.10.2026'}, 'long.pdf')
        data = extract_data(filled)
        student = data['students'][0]
        self.assertEqual((student['phone'], student['group_code'], student['course']), ('+00 001', '001-А', '03'))
        self.assertEqual((student['task'], student['schedule']), (long_text, long_text))
        self.assertEqual(data['date_filled'], ' 07.10.2026')

    def test_edit_and_clear_after_save(self):
        copy, identifier = prepare_copy(self.blank, self.dir / 'copy.pdf', teacher_name='Вымышленный П. П.',
                                        teacher_department='Кафедра физики')
        first = self.fill(copy, {'achievements.1.text': 'Первое', 'achievements.2.text': 'Второе',
                                 'student.schedule': 'Пн 10:00', 'student.middle_name': 'Иванович'}, 'first.pdf')
        second = self.fill(first, {'achievements.1.text': '', 'student.schedule': '', 'student.middle_name': ''},
                           'second.pdf')
        data = extract_data(second)
        self.assertEqual(data['teacher']['department'], 'Кафедра физики')
        student = data['students'][0]
        self.assertEqual(student['id'], identifier)
        self.assertEqual(student['achievements'], [{'id': 'achievement-2', 'text': 'Второе'}])
        self.assertEqual((student['schedule'], student['middle_name']), ('', ''))

    def test_viewer_line_breaks(self):
        copy, _ = prepare_copy(self.blank, self.dir / 'copy.pdf')
        writer = PdfWriter(clone_from=PdfReader(copy))
        fields = dict(iter_terminal_fields(writer.root_object['/AcroForm']['/Fields']))
        # Acrobat stores line breaks as CR.
        fields['student.schedule'][NameObject('/V')] = TextStringObject('Пн\rСр\r\nПт')
        target = self.dir / 'viewer.pdf'
        writer.write(target)
        self.assertEqual(extract_data(target)['students'][0]['schedule'], 'Пн\nСр\nПт')

    def test_prepare_copy_ids_and_no_overwrite(self):
        first, id1 = prepare_copy(self.blank, self.dir / 'a.pdf')
        _, id2 = prepare_copy(self.blank, self.dir / 'b.pdf')
        self.assertNotEqual(id1, id2)
        with self.assertRaisesRegex(ValueError, 'уже есть ID'):
            prepare_copy(first, self.dir / 'c.pdf')
        with self.assertRaises(FileExistsError):
            prepare_copy(self.blank, first)
        with self.assertRaises(FileExistsError):
            build_pdf(self.blank)

    def test_reject_draft01_xfa_and_plain(self):
        draft01 = DRAFTS / 'prepod_vnok_info-v2.0-draft01.pdf'
        if draft01.exists():
            with self.assertRaisesRegex(ValueError, 'v2.0-draft01'):
                extract_data(draft01, assign_id=True)
        writer = PdfWriter()
        writer.add_blank_page(100, 100)
        plain = self.dir / 'plain.pdf'
        writer.write(plain)
        with self.assertRaisesRegex(ValueError, 'нет полей формы'):
            extract_data(plain)
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from build_form import build_pdf as build_xfa
        with self.assertRaisesRegex(ValueError, 'XFA'):
            extract_data(build_xfa(self.dir / 'xfa.pdf'))


if __name__ == '__main__':
    unittest.main()
