#!/usr/bin/env python3
"""Generate filled example PDFs of the one-student form (v2.0); expected results are kept in CASES.

All data are fictional; all teachers belong to one department. Each case gives the expected extraction
(schema 2.0) and, where the PDF holds a different raw value (a Firefox ISO date, Acrobat CR line breaks),
the raw value for the PDF. Expected check messages are written by hand, not taken from extract_static.py,
so the examples test the processing instead of mirroring it. Only the PDFs are written; test_examples.py
compares the extraction with these expectations.
"""
import argparse
import json
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'src' / 'static'))

from pypdf import PdfReader, PdfWriter  # noqa: E402
from pypdf.generic import NameObject, TextStringObject  # noqa: E402

from acroform import iter_terminal_fields, set_values  # noqa: E402
from prepare_copy import prepare_copy  # noqa: E402

FORM = HERE.parent / 'output' / 'drafts' / 'prepod_vnok_info-v2.0-draft04.pdf'
DEPARTMENT = 'Кафедра прикладной математики и информатики'
STUDENT_KEYS = ('last_name', 'first_name', 'middle_name', 'course', 'group_code', 'phone', 'email', 'task',
                'schedule', 'expected_results', 'status', 'notes')
NO_ID = ('ID анкеты не назначен. Готовьте копии командой prepare_copy.py или укажите --assign-id '
         'для временного идентификатора.')

TEACHERS = {
    'head': ('Белозёрова Марина Викторовна', 'Заведующий кафедрой, доктор физико-математических наук, профессор'),
    'prof': ('Сорокопудов Геннадий Ильич', 'Профессор, доктор технических наук'),
    'docent': ('Кочетов Дмитрий Арсеньевич', 'Доцент, кандидат технических наук'),
    'senior': ('Ладыгина Оксана Рафаэлевна', 'Старший преподаватель'),
    'assistant': ('Мирошниченко Алла Евгеньевна', 'Ассистент'),
}


def teacher(key):
    if key is None:
        return {'full_name': '', 'position': '', 'department': ''}
    full_name, position = TEACHERS[key]
    return {'full_name': full_name, 'position': position, 'department': DEPARTMENT}


def student(**fields):
    data = dict.fromkeys(STUDENT_KEYS, '')
    data['achievements'] = []
    data.update(fields)
    data['achievements'] = [{'id': f'achievement-{row}', 'text': text} for row, text in data['achievements']]
    return data


LONG_TASK = '\n'.join([
    'Тема: «Распознавание рукописных математических формул с помощью нейронных сетей».',
    '',
    '1. Обзор литературы (до 15.11.2026).',
    'Изучить не менее 20 источников за последние 10 лет.',
    'Составить аннотированный список и сравнительную таблицу методов.',
    '',
    '2. Подготовка данных (до 20.12.2026).',
    'Собрать и разметить набор из 2000 рукописных формул студентов-добровольцев.',
    'Разделить набор на обучающую, проверочную и тестовую части.',
    '',
    '3. Обучение моделей (февраль — март 2027).',
    'Реализовать модель «кодировщик — декодировщик» на PyTorch.',
    'Сравнить её с открытой базовой моделью по точности и скорости.',
    '',
    '4. Проверка (апрель 2027).',
    'Оценить модель на формулах из конспектов лекций кафедры.',
    '',
    '5. Оформление результатов (май 2027).',
    'Подготовить отчёт по ГОСТ 7.32-2017, тезисы доклада и презентацию.',
])

LONG_SCHEDULE = '\n'.join([
    'Осенний семестр 2026/2027:',
    '• Пн, 15:40–17:10 — очная консультация, ауд. 412.',
    '• Ср, 18:00–19:00 — онлайн-встреча (ссылку присылаю накануне).',
    '• Пт, 10:00–13:00 — работа на вычислительном сервере кафедры,',
    '  компьютерный класс 318 (доступ согласовать по почте).',
    'Сессия (январь): консультации по договорённости.',
    'Весенний семестр: расписание уточним до 01.02.2027.',
    'Отчёт о проделанной работе — каждую вторую пятницу месяца.',
    'При болезни или переносе занятий предупреждать за сутки.',
])

LONG_RESULTS = '\n'.join([
    'Отчёт о НИР (30–40 страниц) с обзором, описанием данных и результатами экспериментов.',
    'Размеченный набор данных и обученная модель с документацией.',
    'Доклад на студенческой научной конференции (апрель 2027).',
    'Статья в сборнике трудов конференции (РИНЦ).',
    'Задел для выпускной квалификационной работы.',
])

OVERFLOW_TASK = '\n'.join(
    ['Тема: «Сравнение алгоритмов поиска кратчайших путей на дорожных графах большого размера».', '']
    + [f'Неделя {week}. {step}' for week, step in enumerate([
        'Изучить алгоритм Дейкстры и его реализацию на двоичной куче.',
        'Изучить алгоритм A* и выбор эвристики для дорожных графов.',
        'Изучить двунаправленный поиск.',
        'Изучить метод иерархий сжатия (Contraction Hierarchies).',
        'Загрузить граф дорог области из открытых данных OpenStreetMap.',
        'Привести граф к единому формату, удалить изолированные вершины.',
        'Реализовать алгоритм Дейкстры на C++.',
        'Реализовать A* с евклидовой эвристикой.',
        'Реализовать двунаправленный поиск.',
        'Реализовать предобработку для иерархий сжатия.',
        'Реализовать запросы по иерархиям сжатия.',
        'Подготовить генератор 10 000 случайных запросов.',
        'Сравнить время ответа всех алгоритмов.',
        'Сравнить расход памяти и время предобработки.',
        'Проверить корректность: ответы всех алгоритмов должны совпадать.',
        'Повторить замеры на графе соседней области.',
        'Построить графики зависимости времени от длины маршрута.',
        'Подготовить таблицы результатов.',
        'Написать раздел «Обзор литературы».',
        'Написать раздел «Реализация».',
        'Написать раздел «Эксперименты».',
        'Подготовить презентацию для семинара кафедры.',
        'Выступить на семинаре и учесть замечания.',
        'Оформить отчёт по ГОСТ 7.32-2017.',
        'Подготовить тезисы на студенческую конференцию.',
        'Выложить код в репозиторий кафедры с инструкцией по запуску.',
        'Подготовить краткую памятку для студентов младших курсов.',
        'Обсудить продолжение работы в выпускной квалификационной работе.',
        'Сдать все материалы руководителю.',
        'Последняя строка задачи: она есть в данных, но не видна в поле при печати.',
    ], 1)])

CASES = [
    {
        'slug': '01-full',
        'description': 'Полностью заполненная форма: все поля, все 10 строк портфолио',
        'teacher': 'head', 'date': '15.09.2026',
        'student': student(
            last_name='Ветрова', first_name='Анастасия', middle_name='Игоревна', course='3',
            group_code='ПМИ-31', phone='+7 (900) 000-00-01', email='a.vetrova@example.org',
            task='Исследовать сходимость итерационных методов решения систем нелинейных уравнений.\n'
                 'Сравнить метод Ньютона, метод простой итерации и метод Бройдена на тестовых задачах.\n'
                 'Подготовить рекомендации по выбору метода в зависимости от свойств системы.',
            schedule='Вторник, 14:00–15:30, ауд. 412.\n'
                     'Четверг, 16:00–17:00 — консультация онлайн.',
            expected_results='Отчёт о НИР, программа на Python с примерами, доклад на семинаре кафедры.',
            status='Выполнен обзор литературы, идёт программная реализация',
            notes='Студентка участвует в олимпиаде по математике; в ноябре возможен перенос двух занятий.',
            achievements=[
                (1, 'Обзор литературы по итерационным методам (35 источников), сентябрь 2026.'),
                (2, 'Реализован метод Ньютона с численным вычислением матрицы Якоби.'),
                (3, 'Реализован метод Бройдена; проведено сравнение на 12 тестовых системах.'),
                (4, 'Доклад «Метод Бройдена на практике» на семинаре кафедры, 02.10.2026.'),
                (5, 'Диплом II степени внутривузовской олимпиады по математике, 2026.'),
                (6, 'Тезисы доклада приняты на студенческую конференцию «Математика и приложения».'),
                (7, 'Сертификат онлайн-курса «Численные методы», 72 часа.'),
                (8, 'Участие в летней школе по вычислительной математике, июль 2026.'),
                (9, 'Подготовлен набор тестовых задач для практикума кафедры.'),
                (10, 'Именная стипендия факультета за успехи в учёбе и науке, 2026/2027.'),
            ]),
        'errors': [], 'warnings': [],
    },
    {
        'slug': '02-minimal',
        'description': 'Только обязательные поля и дата; данные преподавателя (и кафедра) и остальные поля пусты',
        'teacher': None, 'date': '01.10.2026',
        'student': student(last_name='Гусев', first_name='Тимофей', group_code='ПМИ-12',
                           phone='8 900 000 00 02', email='gusev.t@example.com',
                           task='Подготовить реферат по теме «Алгоритмы сортировки и оценка их сложности».'),
        'errors': [], 'warnings': [],
    },
    {
        'slug': '03-no-middle-name',
        'description': 'Иностранный студент без отчества; имя из двух слов',
        'teacher': 'assistant', 'date': '22.09.2026',
        'student': student(
            last_name='Нгуен', first_name='Ван Тхань', course='2', group_code='ПМИ-21и',
            phone='+7-900-000-00-03', email='nguyen.vt@example.ru',
            task='Сравнить библиотеки Python для прогнозирования временных рядов на открытых данных о погоде.',
            schedule='Среда, 12:30–14:00, компьютерный класс 318.',
            expected_results='Аналитическая записка и выступление на секции иностранных студентов.',
            status='Сбор и очистка данных',
            achievements=[(1, 'Собраны данные метеостанций за 2015–2025 годы, устранены пропуски.')]),
        'errors': [], 'warnings': [],
    },
    {
        'slug': '04-long-texts',
        'description': 'Длинные многострочные тексты: задача на 19 строк (около 25 строк в поле), расписание на 9 строк',
        'teacher': 'prof', 'date': '28.09.2026',
        'student': student(
            last_name='Колесников', first_name='Ярослав', middle_name='Денисович', course='4',
            group_code='ПМИ-41', phone='+7 (900) 000-00-04', email='kolesnikov.yd@example.org',
            task=LONG_TASK, schedule=LONG_SCHEDULE, expected_results=LONG_RESULTS,
            status='Выполняется п. 1 (обзор литературы)',
            achievements=[(1, 'Подготовлен план работы на учебный год, утверждён на заседании кафедры.'),
                          (2, 'Получен доступ к вычислительному серверу кафедры с графическими ускорителями.')],
            notes='План работы может быть скорректирован после обсуждения\nна заседании кафедры в декабре.'),
        'errors': [], 'warnings': [],
    },
    {
        'slug': '05-special-chars',
        'description': 'Сложные символы: ё/Ё, ъ, «», —, №, ’, ≥, ¹, неразрывный пробел, ведущие нули, дефис в фамилии',
        'teacher': 'senior', 'date': '05.10.2026',
        'student': student(
            last_name='Д’Артаньян-Ёлкина', first_name='Алёна', middle_name='Объедковна', course='1',
            group_code='007-ПМИ/01', phone='+7 (900) 000-00-05', email='alyona.d-art+nir@example.ru',
            task='Лабораторная работа № 3 по методике «Б» — сортировка слиянием и оценка O(n log n).\n'
                 'Объём данных — 10⁶ записей; доля верных ответов ≥ 99 %.',
            schedule='Пн/Чт — 08:30–10:05, ауд. № 0105.\nСб — по согласованию (не ранее 10:00).',
            expected_results='Программа «№ 3-Б», отчёт и таблица замеров (см. сноску¹).',
            status='Ждём доступа к серверу — с 12.10',
            achievements=[(1, 'Пройден инструктаж по работе в компьютерном классе (журнал № 017, 01.09.2026).')],
            notes='¹ Замеры — на сервере кафедры; запись через ауд. № 412.'),
        'errors': [], 'warnings': [],
    },
    {
        'slug': '06-firefox-iso-date',
        'description': 'Дата в PDF записана как 2026-09-30 (так сохраняет Firefox); в JSON — 30.09.2026',
        'teacher': 'docent', 'date': '30.09.2026', 'pdf_values': {'meta.date_filled': '2026-09-30'},
        'student': student(
            last_name='Бондаренко', first_name='Кирилл', middle_name='Олегович', course='5',
            group_code='ПМИ-51', phone='+7 (900) 000-00-06', email='k.bondarenko@example.com',
            task='Спроектировать базу данных учёта научных работ студентов кафедры и реализовать её на PostgreSQL.',
            schedule='Пятница, 17:20–18:50, компьютерный класс 315.',
            expected_results='Схема базы данных, скрипты создания и наполнения, отчёт.',
            status='Схема согласована, идёт реализация',
            achievements=[(1, 'Согласована логическая схема базы данных (12 таблиц).')]),
        'errors': [], 'warnings': [],
    },
    {
        'slug': '07-portfolio-gaps',
        'description': 'Портфолио с пропусками: заполнены строки 1, 4 и 7; номера строк сохраняются в id',
        'teacher': 'assistant', 'date': '29.09.2026',
        'student': student(
            last_name='Захарченко', first_name='Илья', middle_name='Романович', course='4',
            group_code='ПМИ-412к', phone='+7 (900) 000-00-07', email='zakharchenko.ir@example.org',
            task='Оценить точность фильтра Калмана при объединении данных двух датчиков на модельных траекториях.',
            schedule='Ежедневно в часы самоподготовки, 19:00–20:30, компьютерный класс 318.',
            expected_results='Отчёт, выступление на научной конференции курсантов.',
            status='Обработка результатов моделирования',
            achievements=[(1, 'Выполнено моделирование 500 траекторий.'),
                          (4, 'Грамота за участие в научной конференции курсантов, 2026.'),
                          (7, 'Опубликованы тезисы в сборнике конференции.')],
            notes='Курсант. Строки портфолио 2, 3, 5, 6 очищены после уточнения сведений.'),
        'errors': [], 'warnings': [],
    },
    {
        'slug': '08-course-warning',
        'description': 'Курс указан римской цифрой «II»: предупреждение, ошибок нет',
        'teacher': 'head', 'date': '18.09.2026',
        'student': student(
            last_name='Тарасова', first_name='Полина', middle_name='Андреевна', course='II',
            group_code='ПМИ-22', phone='+7 (900) 000-00-08', email='tarasova.pa@example.ru',
            task='Изучить теорию графов и решить задачи о кратчайших путях из подборки кафедры.',
            schedule='Понедельник, 13:00–14:00, ауд. 410.',
            status='Изучение литературы'),
        'errors': [], 'warnings': ["Курс: ожидается целое число от 1 до 6, указано 'II'."],
    },
    {
        'slug': '09-bad-email-and-date',
        'description': 'Неверный email (без домена после @) и несуществующая дата 31.02.2026',
        'teacher': 'docent', 'date': '31.02.2026',
        'student': student(
            last_name='Филиппова', first_name='Дарья', middle_name='Сергеевна', course='3',
            group_code='ПМИ-32', phone='+7 (900) 000-00-09', email='filippova.ds@',
            task='Построить регрессионную модель посещаемости библиотеки по данным учебного кейса.',
            status='Начало работы'),
        'errors': ["Дата заполнения: ожидается существующая дата в формате ДД.ММ.ГГГГ, указано '31.02.2026'.",
                   'Электронная почта: неверный формат адреса.'],
        'warnings': [],
    },
    {
        'slug': '10-missing-required',
        'description': 'Не заполнены обязательные «Телефон» и «Задача»',
        'teacher': 'senior', 'date': '07.10.2026',
        'student': student(
            last_name='Абрамов', first_name='Никита', middle_name='Львович', course='2',
            group_code='ПМИ-23', email='abramov.nl@example.com',
            schedule='Задачу и время встреч согласуем на первой консультации.',
            status='Не начато'),
        'errors': ['Телефон — обязательное поле не заполнено.',
                   'Задача — обязательное поле не заполнено.'],
        'warnings': [],
    },
    {
        'slug': '11-same-teacher',
        'description': 'Третий студент того же преподавателя, что в примерах 01 и 08 (проверка группировки)',
        'teacher': 'head', 'date': '02.10.2026',
        'student': student(
            last_name='Островский', first_name='Лев', middle_name='Маркович', course='5',
            group_code='ПМИ-51', phone='+7 (900) 000-00-11', email='l.ostrovsky@example.org',
            task='Исследовать устойчивость разностных схем для уравнения теплопроводности\n'
                 'и подготовить методические указания к практикуму.',
            schedule='Вторник, 15:40–17:10, ауд. 412 (после консультации А. Ветровой).',
            expected_results='Методические указания и программа-демонстрация.',
            status='Черновик методических указаний готов на 60 %',
            achievements=[(1, 'Победитель конкурса студенческих научных работ факультета, 2026.'),
                          (2, 'Статья в сборнике «Вычислительные технологии в образовании».')]),
        'errors': [], 'warnings': [],
    },
    {
        'slug': '12-cadet-6th-course',
        'description': 'Курсант 6-го курса (верхняя граница диапазона), служебные формулировки',
        'teacher': 'assistant', 'date': '06.10.2026',
        'student': student(
            last_name='Ермаков', first_name='Святослав', middle_name='Игоревич', course='6',
            group_code='ПМИ-611к', phone='+7 (900) 000-00-12', email='ermakov.si@example.ru',
            task='Разработать программный модуль планирования учебных занятий подразделения\n'
                 'с учётом ограничений по аудиториям и нарядам.',
            schedule='Во время самостоятельной подготовки по распорядку дня, 17:00–19:00.\n'
                     'Консультации — по согласованию с командиром курса.',
            expected_results='Программный модуль и пояснительная записка к выпускной работе.',
            status='Реализован алгоритм составления расписания, идёт тестирование',
            achievements=[(1, 'Рационализаторское предложение принято к внедрению в учебном отделе.')],
            notes='Курсант. Увольнение в город — по выходным; встречи в выходные не назначать.'),
        'errors': [], 'warnings': [],
    },
    {
        'slug': '13-acrobat-line-breaks',
        'description': 'Переводы строк \\r и \\r\\n в PDF (так записывает Acrobat); в JSON — \\n',
        'teacher': 'senior', 'date': '24.09.2026',
        'pdf_values': {'student.schedule': 'Понедельник, 10:00–11:30, ауд. 410.\rСреда, 12:00–13:00, онлайн.\r\n'
                                           'Пятница — по договорённости.',
                       'student.task': 'Реализовать структуру данных «префиксное дерево».\r\n'
                                       'Сравнить её со словарём Python по памяти и скорости.'},
        'student': student(
            last_name='Соловьёва', first_name='Мария', middle_name='Константиновна', course='2',
            group_code='ПМИ-21', phone='+7 (900) 000-00-13', email='soloveva.mk@example.com',
            task='Реализовать структуру данных «префиксное дерево».\n'
                 'Сравнить её со словарём Python по памяти и скорости.',
            schedule='Понедельник, 10:00–11:30, ауд. 410.\nСреда, 12:00–13:00, онлайн.\nПятница — по договорённости.',
            expected_results='Программа и отчёт с замерами.',
            status='Реализация завершена'),
        'errors': [], 'warnings': [],
    },
    {
        'slug': '14-text-overflow',
        'description': 'Задача длиннее видимой области поля (32 строки): при печати видна часть, извлекается весь текст',
        'teacher': 'prof', 'date': '25.09.2026',
        'student': student(
            last_name='Лазарев', first_name='Глеб', middle_name='Анатольевич', course='4',
            group_code='ПМИ-42', phone='+7 (900) 000-00-14', email='lazarev.ga@example.org',
            task=OVERFLOW_TASK,
            schedule='Четверг, 14:00–15:30, ауд. 412.',
            expected_results='Отчёт, код в репозитории кафедры, доклад на семинаре.',
            status='Неделя 5: загрузка графа дорог',
            notes='Полный план работы — в поле «Задача»; при печати он виден не целиком.'),
        'errors': [], 'warnings': [],
    },
    {
        'slug': '15-empty-date',
        'description': 'Дата заполнения не указана: поле необязательное, ошибки нет',
        'teacher': 'assistant', 'date': '',
        'student': student(
            last_name='Кузьмина', first_name='Вероника', middle_name='Павловна', course='1',
            group_code='ПМИ-11', phone='+7 (900) 000-00-15', email='kuzmina.vp@example.ru',
            task='Подготовить доклад «История вычислительной техники в России» для кружка первокурсников.',
            schedule='Раз в две недели, среда, 15:00, ауд. 410.',
            status='Подбор источников'),
        'errors': [], 'warnings': [],
    },
    {
        'slug': '16-course-with-word',
        'description': 'Курс указан как «1 курс»: предупреждение, ошибок нет',
        'teacher': 'assistant', 'date': '03.10.2026',
        'student': student(
            last_name='Галиев', first_name='Тимур', middle_name='Ренатович', course='1 курс',
            group_code='ПМИ-13', phone='+7 (900) 000-00-16', email='galiev.tr@example.com',
            task='Решить 20 задач по комбинаторике из сборника кафедры и оформить решения в LaTeX.',
            schedule='Четверг, 13:00–14:00, ауд. 410.',
            status='Решено 8 задач из 20'),
        'errors': [], 'warnings': ["Курс: ожидается целое число от 1 до 6, указано '1 курс'."],
    },
    {
        'slug': '17-date-no-leading-zero',
        'description': 'Дата «7.10.2026» без ведущего нуля (ввод вручную в программе без JavaScript)',
        'teacher': 'senior', 'date': '7.10.2026',
        'student': student(
            last_name='Панкратова', first_name='Евгения', middle_name='Олеговна', course='3',
            group_code='ПМИ-33', phone='+7 (900) 000-00-17', email='pankratova.eo@example.org',
            task='Сравнить методы кластеризации на данных о покупках в учебном интернет-магазине.',
            schedule='Среда, 16:00–17:30, компьютерный класс 318.',
            status='Подготовка данных'),
        'errors': ["Дата заполнения: ожидается существующая дата в формате ДД.ММ.ГГГГ, указано '7.10.2026'."],
        'warnings': [],
    },
    {
        'slug': '18-blank-names',
        'description': 'Фамилия и имя заполнены одними пробелами: две ошибки обязательных полей',
        'teacher': 'assistant', 'date': '04.10.2026',
        'student': student(
            last_name='   ', first_name=' ', middle_name='', course='2',
            group_code='ПМИ-24', phone='+7 (900) 000-00-18', email='student18@example.com',
            task='Изучить основы работы с системой контроля версий Git.',
            status='Не начато'),
        'errors': ['Фамилия — обязательное поле не заполнено.', 'Имя — обязательное поле не заполнено.'],
        'warnings': [],
    },
    {
        'slug': '19-email-with-space',
        'description': 'Email с пробелом внутри «ivanov @example.org»',
        'teacher': 'docent', 'date': '08.10.2026',
        'student': student(
            last_name='Иванов', first_name='Артём', middle_name='Сергеевич', course='3',
            group_code='ПМИ-31', phone='+7 (900) 000-00-19', email='ivanov @example.org',
            task='Написать веб-сервис для проверки домашних заданий по программированию.',
            schedule='Пятница, 15:40–17:10, компьютерный класс 315.',
            status='Выбрана архитектура сервиса'),
        'errors': ['Электронная почта: неверный формат адреса.'], 'warnings': [],
    },
    {
        'slug': '20-no-id',
        'description': 'Копия без ID анкеты (не подготовлена prepare_copy): извлечение без --assign-id невозможно',
        'teacher': 'assistant', 'date': '08.10.2026', 'prepare': False,
        'student': student(
            last_name='Никитина', first_name='Ольга', middle_name='Викторовна', course='2',
            group_code='ПМИ-22', phone='+7 (900) 000-00-20', email='nikitina.ov@example.ru',
            task='Подготовить обзор языков программирования для обучения школьников.',
            status='Начало работы'),
        'errors': [], 'warnings': [], 'fatal': NO_ID,
    },
]


def expected_data(case, index):
    student_data = {'id': f'student-example-{index:02d}' if case.get('prepare', True) else '', **case['student']}
    # Same key order as extract_static.py, so the JSON files match its output byte for byte.
    order = ('id',) + STUDENT_KEYS[:-1] + ('achievements', 'notes')
    return {'schema_version': '2.0', 'form_id': 'prepod_vnok_info', 'date_filled': case['date'],
            'teacher': teacher(case['teacher']), 'students': [{key: student_data[key] for key in order}]}


def field_values(data):
    """Field values that give the expected data; raw PDF values that differ are in case['pdf_values']."""
    values = {'meta.date_filled': data['date_filled']}
    values.update({'teacher.' + key: value for key, value in data['teacher'].items()})
    student_data = data['students'][0]
    values.update({'student.' + key: student_data[key] for key in STUDENT_KEYS})
    for item in student_data['achievements']:
        values[f"achievements.{item['id'].split('-')[-1]}.text"] = item['text']
    return values


def raw_values(case, data):
    """Values exactly as stored in /V of the example PDF."""
    return {**field_values(data), **case.get('pdf_values', {})}


def dump(data):
    """The canonical serialization: exactly what extract_static.py prints."""
    return json.dumps(data, ensure_ascii=False, indent=2) + '\n'


def exit_code(case):
    return 1 if 'fatal' in case else 2 if case['errors'] else 0


def own_files():
    return [HERE / f"{case['slug']}.pdf" for case in CASES]


def build_pdf(case, data, temp):
    if case.get('prepare', True):
        source, _ = prepare_copy(FORM, Path(temp) / f"{case['slug']}.pdf", student_id=data['students'][0]['id'])
    else:
        source = FORM
    writer = PdfWriter(clone_from=PdfReader(source))
    # Appearances are drawn from the normalized text; a raw value (CR line breaks) then replaces only /V,
    # as a viewer that writes CR would leave the field.
    values = field_values(data)
    values.update({name: value for name, value in case.get('pdf_values', {}).items() if '\r' not in value})
    set_values(writer, values)
    fields = dict(iter_terminal_fields(writer.root_object['/AcroForm']['/Fields']))
    for name, value in case.get('pdf_values', {}).items():
        fields[name][NameObject('/V')] = TextStringObject(value)
    pdf = HERE / f"{case['slug']}.pdf"
    with pdf.open('xb') as output:
        writer.write(output)
    return pdf


def generate(force=False):
    existing = [path for path in own_files() if path.exists()]
    if existing and not force:
        raise FileExistsError(f'Файлы уже есть ({len(existing)}, например {existing[0].name}); '
                              'для пересоздания укажите --force.')
    for path in existing:
        path.unlink()
    with tempfile.TemporaryDirectory() as temp:
        for index, case in enumerate(CASES, 1):
            build_pdf(case, expected_data(case, index), temp)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--force', action='store_true', help='Пересоздать уже сгенерированные файлы примеров.')
    args = parser.parse_args()
    try:
        generate(args.force)
        for case in CASES:
            print(f"{case['slug']}.pdf\tкод {exit_code(case)}")
    except Exception as error:
        parser.exit(1, f'Ошибка: {error}\n')
