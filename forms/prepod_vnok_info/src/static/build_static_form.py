#!/usr/bin/env python3
"""Build the static one-student AcroForm PDF (no XFA, JavaScript or buttons).

Layout: label on the left (30 % of the content width), field on the right (70 %).
"""
import argparse
import logging
from pathlib import Path

from pypdf import PdfWriter
from pypdf.generic import (ArrayObject, BooleanObject, DictionaryObject, FloatObject, NameObject,
                           NumberObject, TextStringObject)

from acroform import (FF_DO_NOT_SPELL_CHECK, FF_MULTILINE, FF_READ_ONLY, FF_REQUIRED, FONT_KEY, HIDDEN_FLAG,
                      PRINT_FLAG, EmbeddedFont, number, stream, text_appearance)

logging.getLogger('fontTools.subset').setLevel(logging.ERROR)  # FFTM table notice

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent.parent
FONT = HERE / 'fonts' / 'LiberationSerif-Regular.ttf'
BOLD_FONT = HERE / 'fonts' / 'LiberationSerif-Bold.ttf'
BOLD_KEY = 'SerifBold'
FORM_ID = 'prepod_vnok_info'
SCHEMA_VERSION = '2.0'
FORM_VERSION = '2.0'
TITLE = 'Информация о студенте (курсанте)'
# Fixed limit of this layout; changing it changes the form and needs a new version.
ACHIEVEMENT_ROWS = 10
DATE_FORMAT = 'dd.mm.yyyy'                  # Acrobat date format = ДД.ММ.ГГГГ
SCHEDULE_MIN_H = 110                        # at least 8 lines of 11 pt text

PAGE_W, PAGE_H = 595.28, 841.89
LEFT, RIGHT, TOP, BOTTOM = 42.5, 552.78, 800, 46
WIDTH = RIGHT - LEFT
LABEL_W = round(WIDTH * 0.30, 2)            # left column: labels
FIELD_X = LEFT + LABEL_W                    # right column: fields
FIELD_W = round(RIGHT - FIELD_X, 2)
LABEL_PAD = 8                               # labels never reach the field column
ROW_GAP = 6
LABEL_SIZE, LABEL_LEADING = 10.5, 12.5
FIELD_SIZE = 11
LINE_H = 21                                 # single-line field height
INK, MUTED, ACCENT = '0.1 0.13 0.18', '0.36 0.4 0.45', '0.1 0.27 0.42'
BOX_FILL, BOX_LINE, NOTE_FILL = '0.965 0.975 0.99', '0.6 0.66 0.72', '0.91 0.94 0.97'


def date_actions(date_format):
    """Standard Acrobat date-field actions (the "Date" format category); the only scripts in the form.

    Viewers that run them offer a date picker and reject invalid dates; others ignore them
    and the field stays plain text.
    """
    def action(code):
        return DictionaryObject({NameObject('/S'): NameObject('/JavaScript'), NameObject('/JS'): TextStringObject(code)})
    return DictionaryObject({
        NameObject('/K'): action(f'AFDate_KeystrokeEx("{date_format}");'),
        NameObject('/F'): action(f'AFDate_FormatEx("{date_format}");'),
    })


class FormBuilder:
    def __init__(self, font_path=FONT, bold_path=BOLD_FONT):
        self.writer = PdfWriter()
        self.font = EmbeddedFont(Path(font_path).read_bytes())
        self.bold = EmbeddedFont(Path(bold_path).read_bytes())
        self.font_ref = self.font.add_to(self.writer)
        self.bold_chars = set()
        self.pages = []
        self.parents = {}
        self.top_fields = ArrayObject()
        self.y = TOP

    # Page drawing -----------------------------------------------------------------
    def new_page(self):
        page = self.writer.add_blank_page(PAGE_W, PAGE_H)
        self.pages.append({'page': page, 'ops': [], 'annots': ArrayObject()})
        self.y = TOP

    def ensure(self, height):
        """Start a new page when the next block does not fit."""
        if self.y - height < BOTTOM:
            self.new_page()

    @property
    def ops(self):
        return self.pages[-1]['ops']

    def text(self, x, y, value, size=10, bold=False, color=INK):
        font, key = (self.bold, BOLD_KEY) if bold else (self.font, FONT_KEY)
        if bold:
            self.bold_chars.update(value)
        self.ops.append(f'q BT {color} rg /{key} {number(size)} Tf {number(x)} {number(y)} Td '
                        f'{font.encode(value)} Tj ET Q')

    def lines(self, x, y, lines, size, leading, bold=False, color=INK):
        for line in lines:
            self.text(x, y, line, size, bold, color)
            y -= leading
        return y

    def rect(self, x, y, w, h, fill=None, stroke=None, line=0.6):
        paint = 'B' if fill and stroke else 'f' if fill else 'S'
        colors = (f'{fill} rg ' if fill else '') + (f'{stroke} RG {number(line)} w ' if stroke else '')
        self.ops.append(f'q {colors}{number(x)} {number(y)} {number(w)} {number(h)} re {paint} Q')

    def section(self, title, note=None, keep=LINE_H):
        """Full-width heading (and optional note), kept together with the first row."""
        note_lines = self.font.wrap(note, WIDTH, 9.5) if note else []
        gap = 10 if self.y >= TOP else 22       # no extra space at the top of a page
        self.ensure(gap + 19 + len(note_lines) * 12 + keep)
        self.y -= 10 if self.y >= TOP else gap
        self.text(LEFT, self.y, title, 14, bold=True, color=ACCENT)
        self.ops.append(f'q {ACCENT} RG 0.8 w {number(LEFT)} {number(self.y - 5)} m '
                        f'{number(RIGHT)} {number(self.y - 5)} l S Q')
        self.y -= 17
        if note_lines:
            self.y = self.lines(LEFT, self.y - 3, note_lines, 9.5, 12, color=MUTED) - 1
        self.y -= 2

    def note_box(self, notes, size=9.5, leading=12):
        wrapped = [self.font.wrap(n, WIDTH - 16, size) for n in notes]
        height = sum(len(w) for w in wrapped) * leading + (len(notes) - 1) * 4 + 14
        self.rect(LEFT, self.y - height, WIDTH, height, NOTE_FILL)
        y = self.y - 7 - size * 0.8
        for lines in wrapped:
            y = self.lines(LEFT + 8, y, lines, size, leading) - 4
        self.y -= height + 6

    # Fields ---------------------------------------------------------------------------
    def parent(self, qualified):
        if qualified in self.parents:
            return self.parents[qualified]
        head, _, name = qualified.rpartition('.')
        node = self.writer._add_object(DictionaryObject({
            NameObject('/T'): TextStringObject(name), NameObject('/Kids'): ArrayObject()}))
        if head:
            up = self.parent(head)
            node.get_object()[NameObject('/Parent')] = up
            up.get_object()['/Kids'].append(node)
        else:
            self.top_fields.append(node)
        self.parents[qualified] = node
        return node

    def widget(self, qualified, rect, entries, flags=PRINT_FLAG):
        head, _, name = qualified.rpartition('.')
        page = self.pages[-1]
        entries.update({
            '/Type': NameObject('/Annot'), '/Subtype': NameObject('/Widget'), '/T': TextStringObject(name),
            '/Rect': ArrayObject(FloatObject(round(v, 2)) for v in rect), '/F': NumberObject(flags),
            '/P': page['page'].indirect_reference})
        node = self.writer._add_object(DictionaryObject({NameObject(k): v for k, v in entries.items()}))
        parent = self.parent(head)
        node.get_object()[NameObject('/Parent')] = parent
        parent.get_object()['/Kids'].append(node)
        page['annots'].append(node)

    def row(self, qualified, label, height=LINE_H, multiline=False, required=False, readonly=False,
            value='', size=FIELD_SIZE, spell=True, label_size=LABEL_SIZE, label_bold=True, date_format=None):
        """One grid row: wrapped label in the left 30 %, field in the right 70 %."""
        caption = label + (' *' if required else '')
        leading = label_size / LABEL_SIZE * LABEL_LEADING
        label_lines = (self.bold if label_bold else self.font).wrap(caption, LABEL_W - LABEL_PAD, label_size)
        label_h = len(label_lines) * leading
        row_h = max(height, label_h)
        self.ensure(row_h)
        top = self.y
        ascent = label_size * 0.72
        if multiline or label_h > height:
            first = top - ascent - 3                            # top-aligned
        else:
            first = top - (height - label_h) / 2 - ascent - (leading - label_size) / 2 - 0.5  # centred
        self.lines(LEFT, first, label_lines, label_size, leading, bold=label_bold)
        self.rect(FIELD_X, top - height, FIELD_W, height, None if readonly else BOX_FILL, BOX_LINE)
        flags = (FF_MULTILINE if multiline else 0) | (FF_REQUIRED if required else 0) | \
                (FF_READ_ONLY if readonly else 0) | (0 if spell else FF_DO_NOT_SPELL_CHECK)
        entries = {
            '/FT': NameObject('/Tx'), '/Ff': NumberObject(flags),
            '/DA': TextStringObject(f'/{FONT_KEY} {number(size)} Tf 0 g'),
            '/V': TextStringObject(value), '/TU': TextStringObject(caption),
            '/AP': DictionaryObject({NameObject('/N'): text_appearance(
                self.writer, self.font, self.font_ref, FIELD_W, height, value, size, multiline)}),
        }
        if date_format:
            entries['/AA'] = date_actions(date_format)
        self.widget(qualified, (FIELD_X, top - height, FIELD_X + FIELD_W, top), entries)
        self.y = top - row_h - ROW_GAP

    def hidden(self, qualified, description, value=''):
        """Service field kept for processing only: hidden on screen and in print, skipped by Tab."""
        rect = (LEFT, 8, LEFT + 120, 20)   # inside the bottom page margin; never shown
        self.widget(qualified, rect, {
            '/FT': NameObject('/Tx'), '/Ff': NumberObject(FF_READ_ONLY),
            '/DA': TextStringObject(f'/{FONT_KEY} 8 Tf 0 g'),
            '/V': TextStringObject(value), '/TU': TextStringObject(description),
            '/AP': DictionaryObject({NameObject('/N'): text_appearance(
                self.writer, self.font, self.font_ref, rect[2] - rect[0], rect[3] - rect[1], value, 8, False)}),
        }, flags=HIDDEN_FLAG)

    # Output -----------------------------------------------------------------------------
    def finish(self, target, title):
        total = len(self.pages)
        for index, item in enumerate(self.pages, 1):
            item['ops'].append(f'q BT {MUTED} rg /{FONT_KEY} 8.5 Tf {number(LEFT)} 26 Td '
                               f'{self.font.encode(f"{FORM_ID} · версия {FORM_VERSION} · страница {index} из {total}")}'
                               ' Tj ET Q')
        bold_ref = self.bold.add_to(self.writer, self.bold_chars)
        resources = DictionaryObject({NameObject('/Font'): DictionaryObject({
            NameObject('/' + FONT_KEY): self.font_ref, NameObject('/' + BOLD_KEY): bold_ref})})
        for item in self.pages:
            page = item['page']
            page[NameObject('/Contents')] = stream(self.writer, '\n'.join(item['ops']))
            page[NameObject('/Resources')] = resources
            page[NameObject('/Annots')] = item['annots']
            page[NameObject('/Tabs')] = NameObject('/R')
        self.writer.root_object[NameObject('/AcroForm')] = self.writer._add_object(DictionaryObject({
            NameObject('/Fields'): self.top_fields,
            NameObject('/DR'): DictionaryObject({NameObject('/Font'): DictionaryObject({
                NameObject('/' + FONT_KEY): self.font_ref})}),
            NameObject('/DA'): TextStringObject(f'/{FONT_KEY} {FIELD_SIZE} Tf 0 g'),
        }))
        root = self.writer.root_object
        root[NameObject('/Lang')] = TextStringObject('ru-RU')
        root[NameObject('/ViewerPreferences')] = DictionaryObject({NameObject('/DisplayDocTitle'): BooleanObject(True)})
        self.writer.pdf_header = '%PDF-1.7'
        self.writer.add_metadata({'/Title': title, '/Subject': f'{FORM_ID}: static AcroForm, one student',
                                  '/Author': FORM_ID})
        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as output:
            self.writer.write(output)
        return target


def build_pdf(target, font_path=FONT, bold_path=BOLD_FONT):
    form = FormBuilder(font_path, bold_path)
    form.new_page()
    form.y -= 16
    form.text(LEFT, form.y, TITLE, 20, bold=True, color=ACCENT)
    form.y -= 17
    form.text(LEFT, form.y, f'Один файл — один студент (курсант). Версия формы {FORM_VERSION}, черновик.', 10.5,
              color=MUTED)
    form.y -= 12
    form.note_box([
        'Щёлкните в поле и введите текст. Поля со звёздочкой (*) обязательны. Для каждого студента (курсанта) '
        'заполняется отдельная копия этого файла.',
        'Сохранение: Adobe Acrobat Reader — «Файл → Сохранить»; Chrome и Edge — «Скачать» → «С изменениями»; '
        'Firefox — кнопка «Сохранить»; «Просмотр» macOS — «Файл → Сохранить». Сохранённый файл можно открыть '
        'снова и продолжить заполнение.',
        'Не используйте «Печать → Сохранить как PDF»: введённые данные перестанут быть полями формы.',
    ])
    form.row('meta.date_filled', 'Дата заполнения (ДД.ММ.ГГГГ)', spell=False, date_format=DATE_FORMAT)

    form.section('Преподаватель')
    form.row('teacher.full_name', 'ФИО преподавателя')
    form.row('teacher.position', 'Должность')
    form.row('teacher.department', 'Кафедра')

    form.section('Студент (курсант)')
    form.row('student.last_name', 'Фамилия', required=True)
    form.row('student.first_name', 'Имя', required=True)
    form.row('student.middle_name', 'Отчество')
    form.row('student.course', 'Курс', spell=False)
    form.row('student.group_code', 'Шифр группы', required=True, spell=False)
    form.row('student.phone', 'Телефон', required=True, spell=False)
    form.row('student.email', 'Электронная почта', required=True, spell=False)
    form.row('student.status', 'Текущий статус выполнения задания')

    form.section('Работа со студентом (курсантом)',
                 'Опишите расписание в свободной форме: режим работы, дни недели, время и место (аудиторию).',
                 keep=SCHEDULE_MIN_H)
    form.row('student.schedule', 'Расписание работы с преподавателем', height=max(SCHEDULE_MIN_H, form.y - BOTTOM),
             multiline=True)

    form.section('Задание', keep=380)
    form.row('student.task', 'Задача, поставленная преподавателем', height=380, multiline=True, required=True)
    form.row('student.expected_results', 'Ожидаемые результаты', height=max(200, form.y - BOTTOM), multiline=True)

    form.section('Портфолио (достижения)',
                 f'До {ACHIEVEMENT_ROWS} достижений, одно достижение в строке. Пустые строки не учитываются. '
                 'Если строк не хватает, перечислите остальное в «Примечании».', keep=28)
    for row in range(1, ACHIEVEMENT_ROWS + 1):
        form.row(f'achievements.{row}.text', f'Достижение {row}', height=28, multiline=True, size=10)

    form.section('Примечание', keep=150)
    form.row('student.notes', 'Примечание', height=max(150, form.y - BOTTOM), multiline=True)

    # Service data for processing: not shown in the form (hidden fields, not printed).
    form.hidden('meta.form_id', 'Служебное: идентификатор формы', FORM_ID)
    form.hidden('meta.schema_version', 'Служебное: версия схемы данных', SCHEMA_VERSION)
    form.hidden('student.id', 'Служебное: ID анкеты (заполняет prepare_copy.py)')

    return form.finish(target, TITLE)


def next_draft():
    drafts = PROJECT / 'output' / 'drafts'
    index = 1
    while (drafts / f'{FORM_ID}-v{FORM_VERSION}-draft{index:02}.pdf').exists():
        index += 1
    return drafts / f'{FORM_ID}-v{FORM_VERSION}-draft{index:02}.pdf'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='Новый PDF; по умолчанию следующий черновик в output/drafts/.')
    parser.add_argument('--font', type=Path, default=FONT, help='Шрифт полей и текста (встраивается полностью).')
    parser.add_argument('--bold-font', type=Path, default=BOLD_FONT, help='Жирный шрифт подписей (подмножество).')
    args = parser.parse_args()
    print(build_pdf(args.output or next_draft(), args.font, args.bold_font))
