// Unit checks of the actual form script with a small XFA API test double.
// These checks do not test a viewer's data binding, layout, or Save command.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {test} = require('node:test');

function setup() {
    const students = [];
    const messages = [];
    const state = {confirmation: 4, focus: null};
    const list = array => ({length: array.length, item: index => array[index]});
    function record(name, fields = {}) {
        const values = Object.fromEntries(Object.entries({id: '', ...fields}).map(([key, value]) => [key, {rawValue: value}]));
        const entries = [];
        return {name, values, entries,
            resolveNode(key) { return values[key] || null; },
            resolveNodes(key) { assert.equal(key, 'schedule.entry[*]'); return list(entries); }
        };
    }
    const root = {resolveNodes(key) { assert.equal(key, 'students.student[*]'); return list(students); }};
    const script = vm.createContext({xfa: {
        form: {resolveNode(key) { assert.equal(key, 'formData'); return root; }, recalculate() {}},
        layout: {relayout() {}},
        host: {
            messageBox(message, title, icon, buttons) {
                messages.push(message);
                return buttons === 2 ? state.confirmation : 1;
            },
            setFocus(field) { state.focus = field; }
        }
    }});
    vm.runInContext(fs.readFileSync(path.join(__dirname, 'form.js'), 'utf8'), script);
    const manager = {
        addInstance() {
            const item = record('student', {full_name: '', group_code: '', phone: '', email: '', task: ''});
            Object.defineProperty(item, 'index', {get() { return students.indexOf(item); }});
            item.instanceManager = manager;
            students.push(item);
            return item;
        },
        removeInstance(index) { students.splice(index, 1); }
    };
    const container = {resolveNode(name) { assert.equal(name, '_student'); return manager; }};
    return {script, students, messages, state, record, container};
}

test('three students: cancelled deletion, confirmed middle deletion, add again', () => {
    const s = setup();
    for (let i = 0; i < 3; i++) {
        s.script.addRecord(s.container, 'student');
        s.students[i].values.full_name.rawValue = 'Студент ' + i;
    }
    const ids = s.students.map(student => student.values.id.rawValue);
    assert.equal(new Set(ids).size, 3);
    s.state.confirmation = 3;
    s.script.removeRecord(s.students[1]);
    assert.equal(s.students.length, 3);
    s.state.confirmation = 4;
    s.script.removeRecord(s.students[1]);
    assert.deepEqual(s.students.map(student => student.values.id.rawValue), [ids[0], ids[2]]);
    assert.deepEqual(s.students.map(student => student.values.full_name.rawValue), ['Студент 0', 'Студент 2']);
    s.script.addRecord(s.container, 'student');
    assert.equal(s.students.length, 3);
    assert.ok(!ids.includes(s.students[2].values.id.rawValue));
    assert.equal(s.state.focus, s.students[2].values.full_name);
});

test('existing identifiers survive initialization', () => {
    const s = setup();
    const item = s.record('student', {id: 'student-saved'});
    s.script.ensureId(item);
    assert.equal(item.values.id.rawValue, 'student-saved');
});

test('exactly five required fields; teacher and optional fields can be blank', () => {
    const s = setup();
    s.script.addRecord(s.container, 'student');
    assert.equal(s.script.validateForm(), false);
    assert.equal((s.messages.at(-1).match(/обязательное поле/g) || []).length, 5);
    Object.entries({full_name:'Примеров Иван', group_code:'001-А', phone:'+00 001', email:'student@example.org', task:'Первая строка\nВторая строка'}).forEach(([key,value]) => {s.students[0].values[key].rawValue=value;});
    assert.equal(s.script.validateForm(), true);
    assert.equal(s.students[0].values.phone.rawValue, '+00 001');
    assert.equal(s.students[0].values.group_code.rawValue, '001-А');
    s.students[0].values.email.rawValue = 'wrong@';
    assert.equal(s.script.validateForm(), false);
    assert.match(s.messages.at(-1), /проверьте email/);
    assert.match(s.messages.at(-1), /Незавершённую форму можно сохранить/);
});

test('empty list is valid as a draft but not complete', () => {
    const s = setup();
    assert.equal(s.script.validateForm(), false);
    assert.match(s.messages.at(-1), /хотя бы одного/);
});

test('schedule and achievement IDs are stable and distinct', () => {
    const s = setup();
    for (const name of ['entry', 'achievement']) {
        const items = [];
        const container = {resolveNode(key) {
            assert.equal(key, '_' + name);
            return {addInstance() { const item = s.record(name, {mode:'', text:''}); items.push(item); return item; }};
        }};
        s.script.addRecord(container, name);
        s.script.addRecord(container, name);
        const before = items.map(item => item.values.id.rawValue);
        items.forEach(item => s.script.ensureId(item));
        assert.deepEqual(items.map(item => item.values.id.rawValue), before);
        assert.notEqual(before[0], before[1]);
    }
});
