// XFA client-side script object. No network or filesystem access.
function root() { return xfa.form.resolveNode('formData'); }
function text(node) { return node && node.rawValue !== null ? String(node.rawValue) : ''; }
function showHost(field) {
    field.rawValue = 'Сценарии формы работают: ' + xfa.host.name + ' ' + xfa.host.appType + ' ' + xfa.host.version + '.';
    field.font.fill.color.value = '30,110,60';
}
function nonempty(node) { return /\S/.test(text(node)); }
function ensureId(record) {
    var field = record.resolveNode('id');
    if (field && !nonempty(field)) {
        field.rawValue = record.name + '-' + new Date().getTime().toString(36) + '-' +
            Math.floor(Math.random() * 0x100000000).toString(36) + '-' +
            Math.floor(Math.random() * 0x100000000).toString(36);
    }
}
function addRecord(container, name) {
    var manager = container.resolveNode('_' + name);
    var record = manager.addInstance(true);
    if (!record) {
        xfa.host.messageBox('Не удалось добавить запись.', 'Научная работа', 0, 0);
        return;
    }
    ensureId(record);
    xfa.form.recalculate(1);
    xfa.layout.relayout();
    var field = record.resolveNode(name === 'student' ? 'full_name' : name === 'entry' ? 'mode' : 'text');
    if (field) xfa.host.setFocus(field);
}
function removeRecord(record) {
    var result = xfa.host.messageBox('Удалить эту запись и все её данные?', 'Удаление записи', 2, 2);
    if (result !== 4) return;
    record.instanceManager.removeInstance(record.index);
    xfa.form.recalculate(1);
    xfa.layout.relayout();
}
function validateForm() {
    var students = root().resolveNodes('students.student[*]');
    var errors = [];
    var required = ['full_name', 'group_code', 'phone', 'email', 'task'];
    var labels = ['ФИО', 'Шифр группы', 'Телефон', 'Электронная почта', 'Задача'];
    if (!students.length) errors.push('Добавьте хотя бы одного студента (курсанта).');
    for (var i = 0; i < students.length; i++) {
        var student = students.item(i);
        for (var j = 0; j < required.length; j++) {
            if (!nonempty(student.resolveNode(required[j]))) errors.push('Студент ' + (i + 1) + ': ' + labels[j] + ' — обязательное поле.');
        }
        var email = text(student.resolveNode('email'));
        if (/\S/.test(email) && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) errors.push('Студент ' + (i + 1) + ': проверьте email.');
        var entries = student.resolveNodes('schedule.entry[*]');
        for (var k = 0; k < entries.length; k++) {
            var entry = entries.item(k);
            var from = text(entry.resolveNode('time_from'));
            var to = text(entry.resolveNode('time_to'));
            var pattern = /^(?:|(?:[01][0-9]|2[0-3]):[0-5][0-9])$/;
            if (!pattern.test(from) || !pattern.test(to)) errors.push('Студент ' + (i + 1) + ', занятие ' + (k + 1) + ': время должно быть в формате ЧЧ:ММ.');
        }
    }
    xfa.host.messageBox(errors.length ? errors.join('\n') + '\n\nНезавершённую форму можно сохранить.' : 'Обязательные поля заполнены. Ошибок формата не найдено.', 'Проверка формы', errors.length ? 1 : 3, 0);
    return errors.length === 0;
}
