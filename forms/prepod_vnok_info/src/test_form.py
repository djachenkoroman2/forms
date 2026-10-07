"""Data and PDF packaging checks. These do not emulate an XFA viewer."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from defusedxml.common import DefusedXmlException
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, NameObject

import re
import xml.etree.ElementTree as ET

from build_form import TEMPLATE_NS, build_pdf, datasets, initial_data, template
from extract_data import extract_data, parse_datasets


class FormDataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.pdf = Path(self.temp.name) / 'form.pdf'

    def test_blank_pdf_and_no_overwrite(self):
        build_pdf(self.pdf)
        data = extract_data(self.pdf)
        self.assertEqual(data['teacher'], {'full_name': '', 'position': ''})
        self.assertEqual(len(data['students']), 1)
        self.assertTrue(data['students'][0]['id'])
        self.assertEqual(data['students'][0]['task'], '')
        self.assertEqual(data['students'][0]['schedule'], [])
        resources = PdfReader(self.pdf).trailer['/Root']['/AcroForm']['/DR']
        self.assertIn('/Font', resources)
        for resource in resources['/Font'].values():
            descriptor = resource.get_object().get('/FontDescriptor')
            if descriptor is not None:
                self.assertTrue(descriptor.get_object()['/FontFamily'])
        original = self.pdf.read_bytes()
        with self.assertRaises(FileExistsError):
            build_pdf(self.pdf)
        self.assertEqual(self.pdf.read_bytes(), original)

    def test_fictional_example(self):
        data = json.loads((Path(__file__).parent.parent / 'docs' / 'example-data.json').read_text())
        build_pdf(self.pdf, data)
        self.assertEqual(extract_data(self.pdf), data)

    def test_latest_incremental_revision_and_record_deletion(self):
        data = initial_data()
        for index in range(3):
            student = copy.deepcopy(data['students'][0])
            student.update(id=f'student-{index}', full_name=f'Вымышленный Студент {index}',
                           group_code='001-А', phone='+00 (012) 003-04',
                           task=('Длинный текст <задачи> & детали\n' * 1500))
            if index == 0:
                data['students'][0] = student
            else:
                data['students'].append(student)
        build_pdf(self.pdf, data)
        self.assertEqual(extract_data(self.pdf), data)
        data['students'].pop(1)
        data['students'][0]['notes'] = 'Изменение после первого сохранения'
        new_student = initial_data()['students'][0]
        data['students'].append(new_student)
        # Simulate a viewer writing a newer datasets revision, preserving old bytes.
        writer = PdfWriter(self.pdf, incremental=True)
        xfa = writer.root_object['/AcroForm']['/XFA']
        index = next(i for i in range(0, len(xfa), 2) if xfa[i] == 'datasets')
        xfa[index + 1].get_object().set_data(datasets(data))
        latest = self.pdf.with_name('latest.pdf')
        writer.write(latest)
        self.assertEqual(extract_data(latest), data)
        self.assertEqual([s['id'] for s in extract_data(latest)['students']],
                         ['student-0', 'student-2', new_student['id']])

    def test_single_xdp_stream(self):
        data = initial_data()
        data['students'] = []
        build_pdf(self.pdf, data)
        writer = PdfWriter(clone_from=PdfReader(self.pdf))
        xfa = writer.root_object['/AcroForm']['/XFA']
        stream = DecodedStreamObject()
        stream.set_data(b''.join(xfa[i].get_object().get_data() for i in range(1, len(xfa), 2)))
        writer.root_object['/AcroForm'][NameObject('/XFA')] = writer._add_object(stream)
        result = self.pdf.with_name('single.pdf')
        writer.write(result)
        self.assertEqual(extract_data(result), data)

    def test_missing_optional_values_and_empty_lists(self):
        xml = datasets(initial_data()).replace(b'<notes />', b'')
        self.assertEqual(parse_datasets(xml)['students'][0]['notes'], '')
        data = initial_data()
        data['students'] = []
        self.assertEqual(parse_datasets(datasets(data)), data)

    def test_reject_ambiguous_ids_and_wrong_schema(self):
        data = initial_data()
        data['students'].append(copy.deepcopy(data['students'][0]))
        with self.assertRaisesRegex(ValueError, 'идентификатор'):
            parse_datasets(datasets(data))
        data = initial_data()
        data['schema_version'] = '99'
        with self.assertRaisesRegex(ValueError, 'версия схемы'):
            parse_datasets(datasets(data))

    def test_reject_xml_entities_and_plain_pdf(self):
        xml = b'<!DOCTYPE datasets [<!ENTITY file SYSTEM "file:///etc/passwd">]><datasets>&file;</datasets>'
        with self.assertRaises(DefusedXmlException):
            parse_datasets(xml)
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        writer.write(self.pdf)
        with self.assertRaisesRegex(ValueError, 'нет интерактивной'):
            extract_data(self.pdf)



class TemplateTests(unittest.TestCase):
    """Static checks of the XFA template; a viewer is still required to run it."""

    def setUp(self):
        self.root = ET.fromstring(template())
        self.ns = {'x': TEMPLATE_NS}
        self.functions = set(re.findall(r'^function (\w+)\(', (Path(__file__).parent / 'form.js').read_text(), re.M))

    def test_scripts_call_existing_functions(self):
        calls = set()
        for node in self.root.iterfind('.//x:event/x:script', self.ns):
            calls.update(re.findall(r'formData\.logic\.(\w+)\(', node.text))
        self.assertTrue(calls)
        self.assertLessEqual(calls, self.functions)

    def test_add_buttons_target_repeatable_subforms(self):
        parents = {child: parent for parent in self.root.iter() for child in parent}
        tag = '{%s}' % TEMPLATE_NS
        for node in self.root.iterfind('.//x:event/x:script', self.ns):
            match = re.search(r"addRecord\((.+?), '(\w+)'\)", node.text)
            if not match:
                continue
            button = parents[parents[node]]
            container = parents[button] if match.group(1) == 'this.parent' else self.root.find(".//x:subform[@name='students']", self.ns)
            repeated = container.find(f"{tag}subform[@name='{match.group(2)}']")
            self.assertIsNotNone(repeated, match.group(0))
            self.assertEqual(repeated.find(f'{tag}occur').get('max'), '-1')

    def test_host_status_is_not_data(self):
        status = self.root.find(".//x:field[@name='hostStatus']", self.ns)
        self.assertEqual(status.find('x:bind', self.ns).get('match'), 'none')
        self.assertEqual(status.get('relevant'), '-print')
        for button in self.root.iterfind('.//x:field/x:ui/x:button/../..', self.ns):
            self.assertEqual(button.find('x:bind', self.ns).get('match'), 'none')


if __name__ == '__main__':
    unittest.main()
