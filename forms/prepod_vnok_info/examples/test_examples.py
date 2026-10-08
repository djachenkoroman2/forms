"""Checks of the example set: extract_static.py --check on each PDF gives the data, exit code and messages
expected in generate_examples.CASES."""
from pathlib import Path
import subprocess
import sys
import unittest

HERE = Path(__file__).resolve().parent
EXTRACT = HERE.parent / 'src' / 'static' / 'extract_static.py'
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'src' / 'static'))

from generate_examples import CASES, DEPARTMENT, dump, exit_code, expected_data, raw_values  # noqa: E402
from extract_static import read_fields  # noqa: E402


def examples():
    for index, case in enumerate(CASES, 1):
        yield case, expected_data(case, index), HERE / f"{case['slug']}.pdf"


class ExampleTests(unittest.TestCase):
    def test_twenty_pdfs_and_no_json(self):
        self.assertEqual(len(CASES), 20)
        self.assertEqual(sorted(path.name for path in HERE.glob('*.pdf')), [f"{c['slug']}.pdf" for c in CASES])
        self.assertEqual(list(HERE.glob('*.json')), [])

    def test_extract_check(self):
        for case, data, pdf in examples():
            with self.subTest(pdf.name):
                result = subprocess.run([sys.executable, str(EXTRACT), str(pdf), '--check'],
                                        capture_output=True, text=True, encoding='utf-8')
                self.assertEqual(result.returncode, exit_code(case), result.stderr)
                if 'fatal' in case:
                    self.assertEqual(result.stdout, '')
                    self.assertEqual(result.stderr.splitlines(), ['Ошибка извлечения: ' + case['fatal']])
                    continue
                self.assertEqual(result.stdout, dump(data))
                expected = ['Ошибка: ' + m for m in case['errors']] + ['Предупреждение: ' + m for m in case['warnings']]
                self.assertEqual(result.stderr.splitlines(), expected)

    def test_pdf_values(self):
        """Raw /V in the PDFs: ISO date in 06, CR line breaks in 13, no ID in 20."""
        for case, data, pdf in examples():
            with self.subTest(pdf.name):
                fields = read_fields(pdf)
                for name, value in raw_values(case, data).items():
                    self.assertEqual(str(fields[name].get('/V') or ''), value, name)
                self.assertEqual(str(fields['student.id'].get('/V') or ''), data['students'][0]['id'])
        fields = read_fields(HERE / '13-acrobat-line-breaks.pdf')
        self.assertIn('\r', str(fields['student.schedule']['/V']))
        self.assertIn('\r\n', str(fields['student.task']['/V']))

    def test_one_department(self):
        for case, _, pdf in examples():
            with self.subTest(pdf.name):
                department = str(read_fields(pdf)['teacher.department'].get('/V') or '')
                self.assertEqual(department, '' if case['slug'] == '02-minimal' else DEPARTMENT)

    def test_teacher_with_several_students(self):
        teachers = [data['teacher']['full_name'] for _, data, _ in examples()]
        self.assertGreaterEqual(teachers.count('Белозёрова Марина Викторовна'), 3)


if __name__ == '__main__':
    unittest.main()
