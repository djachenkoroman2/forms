#!/usr/bin/env python3
"""Build a dynamic XFA PDF. The PDF viewer, not this script, runs form.js."""
import argparse
from io import BytesIO
from pathlib import Path
import uuid
import xml.etree.ElementTree as ET

from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, BooleanObject, DecodedStreamObject, DictionaryObject, NameObject, NumberObject, TextStringObject
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
TEMPLATE_NS = 'http://www.xfa.org/schema/xfa-template/3.3/'
DATA_NS = 'http://www.xfa.org/schema/xfa-data/1.0/'
DAYS = [('monday', 'Пн'), ('tuesday', 'Вт'), ('wednesday', 'Ср'), ('thursday', 'Чт'), ('friday', 'Пт'), ('saturday', 'Сб'), ('sunday', 'Вс')]


def el(parent, tag, text=None, **attrs):
    child = ET.SubElement(parent, tag, {key: str(value) for key, value in attrs.items()})
    if text is not None:
        child.text = text
    return child


def script(parent, activity, code):
    event = el(parent, 'event', activity=activity, ref='$')
    el(event, 'script', code, contentType='application/x-javascript', runAt='client')


def font(parent, size='10pt', bold=False, color='25,40,55'):
    element = el(parent, 'font', typeface='Arial', size=size, weight='bold' if bold else 'normal')
    el(el(element, 'fill'), 'color', value=color)


def draw(parent, value, height='10mm', size='12pt'):
    item = el(parent, 'draw', w='178mm', h=height)
    el(el(item, 'value'), 'text', value)
    font(item, size, True)
    el(item, 'para', vAlign='middle')
    return item


def field(parent, name, label='', multiline=False, hidden=False, default=None):
    attrs = dict(name=name, w='178mm')
    if hidden:
        attrs.update(presence='hidden', h='0mm')
    elif multiline:
        attrs.update(minH='30mm')
    else:
        attrs.update(h='17mm')
    item = el(parent, 'field', **attrs)
    ui = el(item, 'ui')
    edit = el(ui, 'textEdit', multiLine='1' if multiline else '0', vScrollPolicy='off' if multiline else 'auto')
    border = el(edit, 'border')
    el(el(border, 'edge', thickness='0.4pt'), 'color', value='170,184,196')
    el(el(border, 'fill'), 'color', value='247,250,252')
    el(edit, 'margin', leftInset='2mm', rightInset='2mm', topInset='1mm', bottomInset='1mm')
    font(item)
    el(item, 'para', vAlign='top')
    el(item, 'margin', bottomInset='3mm')
    if label:
        caption = el(item, 'caption', placement='top', reserve='6mm')
        el(el(caption, 'value'), 'text', label)
        font(caption, '9pt', True)
    value = el(item, 'value')
    el(value, 'text', default)
    return item


def button(parent, name, label, code, width='95mm'):
    item = el(parent, 'field', name=name, w=width, h='11mm', relevant='-print')
    el(el(item, 'ui'), 'button', highlight='inverted')
    el(item, 'bind', match='none')
    caption = el(item, 'caption', placement='inline')
    el(el(caption, 'value'), 'text', label)
    font(item, '9pt', True, '24,75,109')
    el(item, 'para', hAlign='center', vAlign='middle')
    border = el(item, 'border')
    el(el(border, 'edge', thickness='0.5pt'), 'color', value='150,178,194')
    el(el(border, 'fill'), 'color', value='229,239,245')
    el(item, 'margin', topInset='1mm', bottomInset='2mm')
    script(item, 'click', code)
    return item


def host_status(parent):
    # Not bound to data. The default text stays visible when the viewer does not run XFA scripts.
    item = el(parent, 'field', name='hostStatus', w='178mm', h='9mm', access='readOnly', relevant='-print')
    el(el(item, 'ui'), 'textEdit')
    el(item, 'bind', match='none')
    font(item, '9pt', True, '150,40,30')
    el(item, 'para', vAlign='middle')
    el(el(item, 'value'), 'text', 'Сценарии формы НЕ работают: кнопки не будут действовать. Откройте файл в Adobe Acrobat Reader или Acrobat.')
    script(item, 'initialize', 'formData.logic.showHost(this);')
    return item


def subform(parent, name, repeat=False):
    item = el(parent, 'subform', name=name, layout='tb', w='178mm')
    # Long cards and lists may continue on the next page.
    el(item, 'keep', intact='none')
    if repeat:
        el(item, 'occur', min='0', max='-1', initial='0')
        script(item, 'initialize', 'formData.logic.ensureId(this);')
        field(item, 'id', hidden=True)
    return item


def template():
    tree = ET.Element('template', xmlns=TEMPLATE_NS)
    root = el(tree, 'subform', name='formData', layout='tb', restoreState='auto', locale='en_US')
    variables = el(root, 'variables')
    el(variables, 'script', (HERE / 'form.js').read_text(encoding='utf-8'), name='logic', contentType='application/x-javascript')
    pages = el(root, 'pageSet')
    page = el(pages, 'pageArea', name='A4', id='A4')
    el(page, 'occur', min='1', max='-1')
    el(page, 'medium', short='210mm', long='297mm', stock='a4')
    el(page, 'contentArea', name='body', x='16mm', y='14mm', w='178mm', h='267mm')
    footer = el(page, 'draw', x='16mm', y='284mm', w='178mm', h='6mm')
    el(el(footer, 'value'), 'text', 'НАУЧНАЯ РАБОТА СО СТУДЕНТАМИ  •  Черновик 1.0')
    font(footer, '8pt', color='100,110,120')
    field(root, 'schema_version', hidden=True, default='1.0')
    field(root, 'form_id', hidden=True, default='prepod_vnok_info')
    draw(root, 'Научная работа со студентами', '14mm', '19pt')
    draw(root, 'Черновик. Заполняйте в Adobe Acrobat Reader / Acrobat (Windows, macOS) или в Microsoft Edge, настроенном по инструкции.', '9mm', '9pt')
    host_status(root)
    draw(root, '* Обязательные поля. Незавершённую форму можно сохранить: «Файл → Сохранить как…».', '9mm', '9pt')
    teacher = subform(root, 'teacher')
    field(teacher, 'full_name', 'ФИО преподавателя')
    field(teacher, 'position', 'Должность')
    button(root, 'checkTop', 'Проверить заполнение', 'formData.logic.validateForm();')
    students = subform(root, 'students')
    button(students, 'addStudent', 'Добавить студента (курсанта)', "formData.logic.addRecord(this.parent, 'student');")
    student = subform(students, 'student', repeat=True)
    draw(student, 'Студент (курсант)', '12mm', '15pt')
    for name, label in [('full_name', 'Полные ФИО *'), ('group_code', 'Шифр группы *'), ('phone', 'Телефон *'), ('email', 'Электронная почта *')]:
        field(student, name, label)
    field(student, 'task', 'Задача, поставленная преподавателем *', multiline=True)
    schedule = subform(student, 'schedule')
    draw(schedule, 'Расписание работы', '10mm', '12pt')
    button(schedule, 'addSchedule', 'Добавить занятие', "formData.logic.addRecord(this.parent, 'entry');")
    entry = subform(schedule, 'entry', repeat=True)
    field(entry, 'mode', 'Режим работы (например, консультация, лабораторная работа)')
    days = el(entry, 'subform', name='weekdays', layout='lr-tb', w='178mm')
    for name, label in DAYS:
        check = el(days, 'field', name=name, w='24mm', h='9mm')
        el(el(check, 'ui'), 'checkButton', size='3mm')
        caption = el(check, 'caption', placement='right', reserve='18mm')
        el(el(caption, 'value'), 'text', label)
        font(check)
        items = el(check, 'items')
        el(items, 'integer', '1')
        el(items, 'integer', '0')
        el(el(check, 'value'), 'integer', '0')
    field(entry, 'time_from', 'Начало (ЧЧ:ММ)')
    field(entry, 'time_to', 'Окончание (ЧЧ:ММ)')
    field(entry, 'room', 'Аудитория / место работы')
    button(entry, 'removeSchedule', 'Удалить занятие', 'formData.logic.removeRecord(this.parent);')
    field(student, 'expected_results', 'Ожидаемые результаты', multiline=True)
    field(student, 'status', 'Текущий статус выполнения задания')
    achievements = subform(student, 'achievements')
    draw(achievements, 'Портфолио', '10mm', '12pt')
    button(achievements, 'addAchievement', 'Добавить достижение', "formData.logic.addRecord(this.parent, 'achievement');")
    achievement = subform(achievements, 'achievement', repeat=True)
    field(achievement, 'text', 'Достижение', multiline=True)
    button(achievement, 'removeAchievement', 'Удалить достижение', 'formData.logic.removeRecord(this.parent);')
    field(student, 'notes', 'Примечание', multiline=True)
    button(student, 'removeStudent', 'Удалить студента (курсанта)', 'formData.logic.removeRecord(this.parent);')
    button(root, 'addStudentEnd', 'Добавить студента (курсанта)', "formData.logic.addRecord(formData.students, 'student');")
    button(root, 'checkEnd', 'Проверить заполнение', 'formData.logic.validateForm();')
    return ET.tostring(tree, encoding='utf-8')


def initial_data():
    return {
        'schema_version': '1.0', 'form_id': 'prepod_vnok_info',
        'teacher': {'full_name': '', 'position': ''},
        'students': [dict(id='student-' + str(uuid.uuid4()), full_name='', group_code='', phone='', email='', task='', schedule=[], expected_results='', status='', achievements=[], notes='')]
    }


def datasets(data):
    packet = ET.Element('xfa:datasets', {'xmlns:xfa': DATA_NS})
    root = el(el(packet, 'xfa:data'), 'formData')
    el(root, 'schema_version', data['schema_version'])
    el(root, 'form_id', data['form_id'])
    teacher = el(root, 'teacher')
    for key, value in data['teacher'].items():
        el(teacher, key, value)
    students = el(root, 'students', **{'xfa:dataNode': 'dataGroup'})
    for value in data['students']:
        student = el(students, 'student')
        for key in ['id', 'full_name', 'group_code', 'phone', 'email', 'task', 'expected_results', 'status', 'notes']:
            el(student, key, value[key])
        schedule = el(student, 'schedule', **{'xfa:dataNode': 'dataGroup'})
        for row in value['schedule']:
            entry = el(schedule, 'entry')
            for key in ['id', 'mode', 'time_from', 'time_to', 'room']:
                el(entry, key, row[key])
            days = el(entry, 'weekdays')
            for day, _ in DAYS:
                el(days, day, '1' if day in row['weekdays'] else '0')
        achievements = el(student, 'achievements', **{'xfa:dataNode': 'dataGroup'})
        for row in value['achievements']:
            item = el(achievements, 'achievement')
            el(item, 'id', row['id'])
            el(item, 'text', row['text'])
    return ET.tostring(packet, encoding='utf-8')


CONFIG = b'''<config xmlns="http://www.xfa.org/schema/xci/3.0/">
<present><pdf><version>1.7</version><adobeExtensionLevel>8</adobeExtensionLevel><renderPolicy>client</renderPolicy><scriptModel>XFA</scriptModel><interactive>1</interactive></pdf><destination>pdf</destination><script><runScripts>client</runScripts></script></present>
<acrobat><acrobat7><dynamicRender>required</dynamicRender></acrobat7><validate>preSubmit</validate></acrobat>
</config>'''


def build_pdf(target, data=None, font_path='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'):
    data = initial_data() if data is None else data
    pdfmetrics.registerFont(TTFont('Fallback', font_path))
    buffer = BytesIO()
    page = canvas.Canvas(buffer, pagesize=A4, invariant=1)
    page.setFillColor(colors.HexColor('#142F43'))
    page.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
    page.setFillColor(colors.white)
    for y, size, text in [
        (735, 20, 'Научная работа со студентами'),
        (686, 13, 'Ваша программа не открыла интерактивную форму.'),
        (649, 11, 'Сохраните файл на компьютер и откройте его'),
        (630, 11, 'в бесплатной программе Adobe Acrobat Reader'),
        (611, 11, '(Windows или macOS): get.adobe.com/reader'),
        (574, 11, 'Microsoft Edge подходит только после настройки'),
        (555, 11, 'администратором (см. инструкцию к форме).'),
        (518, 11, 'Браузеры Chrome, Firefox, Safari, мобильные'),
        (499, 11, 'приложения и «Предпросмотр» macOS не подходят.'),
        (440, 10, 'Не заполняйте и не печатайте эту страницу.'),
    ]:
        page.setFont('Fallback', size)
        page.drawString(42, y, text)
    page.save()
    writer = PdfWriter(clone_from=PdfReader(buffer))
    writer.pdf_header = '%PDF-1.7'
    resources = writer.pages[0]['/Resources']
    for resource in resources['/Font'].values():
        descriptor = resource.get_object().get('/FontDescriptor')
        if descriptor is not None:
            descriptor = descriptor.get_object()
            family = pdfmetrics.getFont('Fallback').face.familyName
            descriptor[NameObject('/FontFamily')] = TextStringObject(family.decode('utf-8') if isinstance(family, bytes) else family)
            descriptor[NameObject('/FontWeight')] = NumberObject(400)
    packets = [
        ('preamble', b'<xdp:xdp xmlns:xdp="http://ns.adobe.com/xdp/">'),
        ('config', CONFIG), ('template', template()), ('datasets', datasets(data)),
        ('postamble', b'</xdp:xdp>')
    ]
    xfa = ArrayObject()
    for name, content in packets:
        stream = DecodedStreamObject()
        stream.set_data(content)
        xfa.extend([TextStringObject(name), writer._add_object(stream)])
    # PDF.js initializes XFA font lookup only when AcroForm exposes DR/Font.
    # Reuse the fallback page resources, including its embedded Cyrillic font.
    acroform = DictionaryObject({
        NameObject('/XFA'): xfa,
        NameObject('/Fields'): ArrayObject(),
        NameObject('/DR'): resources,
    })
    writer.root_object[NameObject('/AcroForm')] = writer._add_object(acroform)
    writer.root_object[NameObject('/NeedsRendering')] = BooleanObject(True)
    writer.root_object[NameObject('/Lang')] = TextStringObject('ru-RU')
    writer.root_object[NameObject('/Extensions')] = DictionaryObject({NameObject('/ADBE'): DictionaryObject({NameObject('/BaseVersion'): NameObject('/1.7'), NameObject('/ExtensionLevel'): NumberObject(8)})})
    writer.add_metadata({'/Title': 'Научная работа со студентами — черновик', '/Subject': 'prepod_vnok_info: dynamic XFA form', '/Author': 'prepod_vnok_info'})
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('xb') as output:
        writer.write(output)
    return target


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--font', default='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
    args = parser.parse_args()
    target = args.output
    if target is None:
        drafts = PROJECT / 'output' / 'drafts'
        index = 1
        while (drafts / f'prepod_vnok_info-v1.0-draft{index:02}.pdf').exists():
            index += 1
        target = drafts / f'prepod_vnok_info-v1.0-draft{index:02}.pdf'
    print(build_pdf(target, font_path=args.font))
