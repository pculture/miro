from miro.dialogs import *

def text_entry_callback():
    return 'Pizza'

test_dialogs = [
        MessageBoxDialog('Hello ' * 100, 'World'),
        ChoiceDialog('Hello', 'You like peas?', BUTTON_YES,
            BUTTON_NO),
        ThreeChoiceDialog('Hello', 'You like peas?', BUTTON_YES,
            BUTTON_NO, BUTTON_SUBMIT_REPORT),
        HTTPAuthDialog('http://getmiro.com/', 'Private ' * 40,
            prefillUser='ben', prefillPassword='god'),
        TextEntryDialog('Hi', 'testing', BUTTON_OK, BUTTON_CANCEL),
        TextEntryDialog('Hi', 'testing', BUTTON_OK, BUTTON_CANCEL,
            text_entry_callback),
        TextEntryDialog('Hi', 'testing', BUTTON_OK, BUTTON_CANCEL,
            fillWithClipboardURL=True),
        CheckboxDialog('Hi', 'testing223', 'keep on rocking', True,
            BUTTON_NO, BUTTON_CLOSE_TO_TRAY),
        CheckboxTextboxDialog('Yo there', "What's Up?",
            'push the button', False, 'PREFILL TEXT',
            BUTTON_DELETE, BUTTON_KEEP_VIDEOS)
        ]

dialog_index = 3

def dialog_callback(dialog, *extra_args):
    print 'got callback: %s' % dialog
    print 'choice: %s' % dialog.choice
    for extra in extra_args:
        print 'extra: %s' % extra
    if isinstance(dialog, HTTPAuthDialog):
        print 'username: %s' % dialog.username
        print 'password: %s' % dialog.password
    elif isinstance(dialog, TextEntryDialog):
        print 'text: %s' % dialog.value
    elif isinstance(dialog, CheckboxTextboxDialog):
        print 'checked: %s' % dialog.checkbox_value
        print 'text: %s' % dialog.textbox_value
    elif isinstance(dialog, CheckboxDialog):
        print 'checked: %s' % dialog.checkbox_value

    print
    print

def run_dialog():
    dialog = test_dialogs[dialog_index]
    dialog.run(dialog_callback)

def run_next_dialog():
    global dialog_index

    dialog_index = (dialog_index + 1) % len(test_dialogs)
    run_dialog()
