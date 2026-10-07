# Поддерживаемые просмотрщики и их настройка

Решение 07.10.2026 ([0003-acrobat-edge-v1.txt](../prompts/0003-acrobat-edge-v1.txt)): форма остаётся динамическим XFA PDF. Целевые среды: Adobe Acrobat Reader / Acrobat и Microsoft Edge. Работа в других браузерах и программах не поддерживается.

Документация проверена 07.10.2026. Ни одна из целевых сред ещё **не проверена фактически**: в среде разработки (Linux) их нет. Статус каждой среды фиксируется в [чек-листе приёмки](acceptance-checklist.md).

## Сводка

| Среда | Основание | Статус |
| --- | --- | --- |
| Adobe Acrobat Reader / Acrobat, Windows | Adobe: XFA-формы полностью поддерживаются в Acrobat и Reader версии 8 и выше [1] | Основная среда. Не проверено |
| Adobe Acrobat Reader / Acrobat, macOS | То же [1] | Основная среда. Не проверено |
| Edge, режим IE с подключаемым модулем Acrobat (Windows) | Политика `ViewXFAPDFInIEModeAllowedOrigins`, Edge ≥ 132 [3] | Предпочтительный вариант для Edge. Не проверено |
| Edge, встроенный просмотрщик с `PDFXFAEnabled` (Windows, macOS) | Политика Edge ≥ 104 [2]; Adobe относит Edge к браузерам с ограниченной поддержкой XFA [1] | Экспериментально. Не проверено |
| Firefox 157 / PDF.js 6.3 | Фактическая проверка draft03 | **Не подходит**: кнопка добавления не работает ([протокол](verification.md)) |
| Chrome, Safari, мобильные просмотрщики, «Предпросмотр» macOS | Adobe: ограниченная поддержка [1] | Не поддерживаются |

## Adobe Acrobat Reader / Acrobat

Требования:

- Windows или macOS, актуальная версия Acrobat Reader (бесплатный) или Acrobat Standard/Pro. Мобильные версии Acrobat Reader не поддерживаются.
- Включён JavaScript: **Установки (Ctrl+K / Cmd+K) → JavaScript → «Включить JavaScript Acrobat»** [4]. Если параметр заблокирован администратором, форма не будет работать.
- Файл выведен из защищённого режима (Protected View) кнопкой **«Включить все функции»**: в этом режиме большинство функций отключено [5]. Альтернатива для организаций — добавить папку с формами в доверенные расположения: **Установки → Безопасность (повышенная) → Привилегированные расположения**.
- Сохранение заполненной формы выполняется командами «Сохранить» / «Сохранить как…». Расширенные права (Reader Extensions) для этого не добавлялись. По документации современный Reader сохраняет данные форм без них, но это требует проверки (пункт 6 чек-листа).

Признак работоспособности: зелёная строка «Сценарии формы работают: Acrobat …» под заголовком. В ней указаны тип и версия программы, которые нужно записать в чек-лист.

## Microsoft Edge

Обе настройки задаёт администратор групповыми политиками или реестром. Пользователь сам их не включает. После изменения политики Edge нужно перезапустить [2][3].

### Вариант А (предпочтительный): режим IE с подключаемым модулем Acrobat

Политика `ViewXFAPDFInIEModeAllowedOrigins`. Только Windows, Edge 132 и новее. В режиме IE XFA-файлы открываются через ActiveX-модуль Adobe Acrobat. **Сам модуль политика не устанавливает**: на компьютере должен быть установлен Acrobat Reader или Acrobat [3]. Фактически форму обрабатывает движок Adobe, поэтому этот вариант ближе всего к основной среде.

Пример реестра (`HKLM`, обязательная политика):

```text
SOFTWARE\Policies\Microsoft\Edge\ViewXFAPDFInIEModeAllowedOrigins\1 = https://forms.example.org/prepod/
SOFTWARE\Policies\Microsoft\Edge\ViewXFAPDFInIEModeAllowedOrigins\2 = file://<сервер-или-папка-с-формами>/
```

Групповая политика: *Administrative Templates / Microsoft Edge / PDF Reader / View XFA-based PDF files using IE Mode for allowed file origin*.

Замечания:

- Адреса выше — примеры. Формат шаблонов URL описан Microsoft [3]. Точную запись для папки или файлового сервера организации нужно проверить при приёмке.
- Альтернативная политика `ViewXFAPDFInIEModeAllowedFileHash` разрешает файлы по хешу. Для этой формы она **не подходит**: каждый сохранённый экземпляр имеет новый хеш, и повторное открытие заполненной формы перестанет попадать под разрешение.
- Режим IE должен быть доступен в организации. Подробности согласуйте с администратором.

### Вариант Б (экспериментальный): встроенный просмотрщик Edge

Политика `PDFXFAEnabled` включает поддержку XFA во встроенном PDF-просмотрщике Edge [2]. Windows и macOS, Edge 104 и новее; Android и iOS не поддерживаются.

- Windows, реестр: `HKLM\SOFTWARE\Policies\Microsoft\Edge`, параметр `PDFXFAEnabled`, `REG_DWORD` = `1`. Групповая политика: *Administrative Templates / Microsoft Edge / XFA support in native PDF reader enabled*.
- macOS: ключ настройки `PDFXFAEnabled` со значением `true` в профиле конфигурации Edge.

Microsoft не описывает в документации политики объём поддержки сценариев XFA, динамических подформ и сохранения. Adobe относит Edge к браузерам с ограниченными возможностями XFA [1]. Microsoft называет XFA устаревшей технологией и рекомендует планировать переход на другие решения [3]. Вариант Б допускается к использованию только после полного прохождения чек-листа в конкретной версии Edge.

## Источники

1. Adobe Experience League — [XFA-based PDF forms in Chrome, Firefox, Internet Explorer, Safari, Edge](https://experienceleague.adobe.com/en/docs/experience-manager-65/content/forms/troubleshooting/xfa-based-forms-in-chrome-firefox-ie-internet-explorter-safari-edge).
2. Microsoft Learn — [PDFXFAEnabled](https://learn.microsoft.com/en-us/deployedge/microsoft-edge-policies/pdfxfaenabled) (страница обновлена 20.05.2026).
3. Microsoft Learn — [ViewXFAPDFInIEModeAllowedOrigins](https://learn.microsoft.com/en-us/deployedge/microsoft-edge-policies/viewxfapdfiniemodeallowedorigins) (страница обновлена 20.05.2026).
4. Adobe Help — [JavaScripts in PDFs as a security risk](https://helpx.adobe.com/acrobat/using/javascripts-pdfs-security-risk.html).
5. Adobe Help — [Enable or disable protected view in Acrobat](https://helpx.adobe.com/acrobat/desktop/protect-documents/use-protected-view/protect-view-mode.html).
