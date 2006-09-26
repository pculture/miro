#import "Generate.h"
#import "Tstate.h"
#import "pystructs.h"
#import "callbacks.h"

@protocol GCallbacks
- (void)endGenerate;
@end

@implementation Generate

#define ANNOUNCEKEY @"AnnounceString"
#define GWINKEY @"GenerateFrame"
#define COMPLETEDIRKEY @"CompleteDir"

- init {
    NSUserDefaults *defaults; 
    NSMutableDictionary *appDefaults;

    [super init];
    [NSBundle loadNibNamed:@"Metainfo" owner:self];
    [gWindow registerForDraggedTypes:[NSArray arrayWithObjects:NSFilenamesPboardType, nil]];

    defaults = [NSUserDefaults standardUserDefaults];
    appDefaults = [NSMutableDictionary
        dictionaryWithObject:@"" forKey:ANNOUNCEKEY];
    [appDefaults setObject:[NSNumber numberWithInt:NSOffState] forKey:COMPLETEDIRKEY];
    [appDefaults setObject:[gWindow stringWithSavedFrame] forKey:GWINKEY];
    [defaults registerDefaults:appDefaults];

    [gWindow setFrameAutosaveName:GWINKEY];
    [gWindow setFrameUsingName:GWINKEY];
    [announce setStringValue:[defaults objectForKey:ANNOUNCEKEY]];
    [subCheck setState:[[defaults objectForKey:COMPLETEDIRKEY] intValue]];
    return self;
}

- (IBAction)generate:(id)sender
{
    NSSavePanel *panel =  [NSSavePanel savePanel];
    NSArray *a;
    NSRange range;
    NSUserDefaults *defaults = [NSUserDefaults standardUserDefaults];

    // do a bunch of checking
    // put up alert sheet if error
    
    [gButton setEnabled:NO];
    if([[announce stringValue] compare:@""] == NSOrderedSame) {
    NSBeginAlertSheet(NSLocalizedString(@"Invalid Tracker URL", @""), nil, nil, nil, gWindow, nil, nil, nil, nil, NSLocalizedString(@"You must enter the tracker URL.  Contact the tracker administrator for the URL.", @""));
    }
    else if (fname == nil) {
        NSBeginAlertSheet(NSLocalizedString(@"Invalid File", @"invalid file chose fo generate"), nil, nil, nil, gWindow, nil, nil, nil, nil, NSLocalizedString(@"You must drag a file or folder into the generate window first.", @"empty file for generate"));
        [gButton setEnabled:YES];
    }
    else {
        [defaults setObject:[announce stringValue] forKey:ANNOUNCEKEY];
        [defaults setObject:[NSNumber numberWithInt:[subCheck state]] forKey:COMPLETEDIRKEY];
        a = [fname pathComponents];
        range.location = 0;
        range.length = [a count] -1;
        if ([subCheck isEnabled] && [subCheck state]) {
            [self prepareGenerateSaveFile:fname];   
        }
        else {
            [panel beginSheetForDirectory:[NSString pathWithComponents:[a subarrayWithRange:range]] file:[[a objectAtIndex:[a count] -1] stringByAppendingString:@".torrent"] modalForWindow:gWindow modalDelegate:self
                didEndSelector:@selector(savePanelDidEnd:returnCode:contextInfo:) contextInfo:panel];
        }
    }
}

- (void)savePanelDidEnd:(NSWindow *)sheet returnCode:(int)returnCode contextInfo:(void  *)contextInfo {
    NSSavePanel *panel = (NSSavePanel *)contextInfo;
    
    NSString *f = [panel filename];
    if(returnCode == 1) {
        [self prepareGenerateSaveFile:f];
    }
    else {
        [gButton setEnabled:YES];
    }
}

- (void) prepareGenerateSaveFile:(NSString *)f {
    NSConnection *conn;
    NSMutableDictionary *dict = [NSMutableDictionary dictionaryWithCapacity:5];
    NSPort *left, *right;
    PyObject *mm, *md, *event;
    
    left = [NSPort port];
    right = [NSPort port];
    conn = [[NSConnection alloc] initWithReceivePort:left sendPort:right];
    [conn setRootObject:self];

    [dict setObject:right forKey:@"receive"];
    [dict setObject:left forKey:@"send"];
    [dict setObject:f forKey:@"f"];
    [dict setObject:fname forKey:@"fname"];
    [dict setObject:[announce stringValue] forKey:@"url"];

    // if subCheck is both enabled and checked
    if ([subCheck isEnabled] && [subCheck state]) {
        [dict setObject:[NSNumber numberWithInt:1] forKey:@"completedir"];
    }
    else {
        [dict setObject:[NSNumber numberWithInt:0] forKey:@"completedir"];
    }
    
    [subCheck setEnabled:NO];
    [progressMeter startAnimation:self];
    [gWindow unregisterDraggedTypes];
    
    PyEval_RestoreThread([[NSApp delegate] tstate]);
    mm = PyImport_ImportModule("threading");
    md = PyModule_GetDict(mm);
    event = PyDict_GetItemString(md, "Event");
    endflag = PyObject_CallFunction(event, "");
    [[NSApp delegate] setTstate:PyEval_SaveThread()];
    
    done = NO;
    [dict setObject:[NSData dataWithBytes:&endflag length:sizeof(PyObject *)] forKey:@"flag"];
    [NSThread detachNewThreadSelector:@selector(doGenerate:) toTarget:[self class]  
    withObject:dict];
    [gButton setTitle:NSLocalizedString(@"Cancel", @"Cancel")];
    [gButton setAction:@selector(cancel:)];
}

- (void)progress:(in float)val
{
    if(!done) {
        [progressMeter setDoubleValue:val];
        [gButton setEnabled:YES];
    }
}

- (void)progressFname:(NSString *)val;
{
    [self displayFile:val];
}

- (void)endGenerate {
    NSFileManager *fm = [NSFileManager defaultManager];
    NSWorkspace *wk = [NSWorkspace sharedWorkspace];
    NSDictionary *dict;

    dict = [fm fileAttributesAtPath:fname traverseLink:YES];

    [self displayFile:fname];

    // if fname is directory and is not file package
    if ([[dict objectForKey:@"NSFileType"] isEqualToString:@"NSFileTypeDirectory"] && ![wk isFilePackageAtPath:fname]) {
        [subCheck setEnabled:YES];
    }
    else {
        [subCheck setEnabled:NO];
    }

    [progressMeter stopAnimation:self];
    [gWindow registerForDraggedTypes:[NSArray arrayWithObjects:NSFilenamesPboardType, nil]];
    [gButton setTitle:NSLocalizedString(@"Generate", @"Generate")];
    [gButton setAction:@selector(generate:)];
    done = YES;
}

- (IBAction)cancel:(id)sender
{
    done = YES;
    PyEval_RestoreThread([[NSApp delegate] tstate]);
    PyObject_CallMethod(endflag, "set", NULL);
    [[NSApp delegate] setTstate:PyEval_SaveThread()];
    [progressMeter setDoubleValue:0.0];
}

+ (void)doGenerate:(NSDictionary *)dict
{
    PyObject *mm, *md;
    PyObject *mmf, *res, *enc, *be, *flag, *display, *displayFname;
    FILE *desc;
    NSString *f, *url, *filename;
    PyThreadState *ts;
    bt_ProxyObject *proxy;
    NSAutoreleasePool *pool = [[NSAutoreleasePool alloc] init];
    id foo;
    ts = PyThreadState_New([[NSApp delegate] tstate]->interp);
    PyEval_RestoreThread(ts);    

    f = [dict objectForKey:@"f"];
    filename = [dict objectForKey:@"fname"];
    url = [dict objectForKey:@"url"];
    proxy = (bt_ProxyObject *)bt_getMetaProxy([dict objectForKey:@"receive"], [dict objectForKey:@"send"]);

    mm = PyImport_ImportModule("BitTorrent.bencode");
    md = PyModule_GetDict(mm);
    be = PyDict_GetItemString(md, "bencode");
    
    [[dict objectForKey:@"flag"] getBytes:&flag];
    
    if ([[dict objectForKey:@"completedir"] intValue] == 0) {
        mm = PyImport_ImportModule("btmakemetafile");
        md = PyModule_GetDict(mm);
        mmf = PyDict_GetItemString(md, "makeinfo");
        display = PyObject_GetAttrString((PyObject *)proxy, "metaprogress");
        res = PyObject_CallFunction(mmf, "siOOi", [filename UTF8String],  262144, flag, display, 1);
        if(res != NULL && res != Py_None) {
            enc = PyObject_CallFunction(be, "{s:O,s:s}", "info", res, "announce", [url UTF8String]);
            if(PyErr_Occurred())
                PyErr_Print();
            else {
                desc = fopen([f UTF8String], "w");
                fwrite(PyString_AsString(enc), sizeof(char), PyString_Size(enc), desc);
                fclose(desc);
                if(enc) {
                    Py_DECREF(enc);
                }
            }
            Py_DECREF(res);
        }
    }
    else {
        mm = PyImport_ImportModule("btcompletedir");
        md = PyModule_GetDict(mm);
        mmf = PyDict_GetItemString(md, "completedir");
        display = PyObject_GetAttrString((PyObject *)proxy, "metaprogress");
        displayFname = PyObject_GetAttrString((PyObject *)proxy, "fnameprogress");
        res = PyObject_CallFunction(mmf, "ssOOOi", [filename UTF8String], [url UTF8String], flag, display, displayFname, 18);
        if(PyErr_Occurred())
            PyErr_Print();
        if(res) {
            Py_DECREF(res);
        }
    }

    ts = PyEval_SaveThread();
    foo = (id)[[NSConnection connectionWithReceivePort:[dict objectForKey:@"receive"]
                    sendPort:[dict objectForKey:@"send"]]
            rootProxy];
    [foo setProtocolForProxy:@protocol(GCallbacks)];
    [foo endGenerate];
    [pool release];
}

- (void)open
{
    [gWindow makeKeyAndOrderFront:self];
}

- (void)displayFile:(NSString *)f
{
    NSImage *icon;
    // lookup + display icon
    icon = [[NSWorkspace sharedWorkspace] iconForFile:f];
    [iconWell setImage:icon];
    // set path field
    [fileField setStringValue:f];

}



// drag protocol methods
- (NSDragOperation)draggingEntered:(id <NSDraggingInfo>)sender
{
    NSString *f;
    NSPasteboard *board;
    NSArray *names;
    
    // get path off pasteboard
    board = [sender draggingPasteboard];
    names = [board propertyListForType:@"NSFilenamesPboardType"];
    if ([names count] > 0) {
        f = [names objectAtIndex:0];
        [self displayFile:f];
        [progressMeter setDoubleValue:0.0];
        return NSDragOperationGeneric;
    }
    return NSDragOperationNone;
}

- (void)draggingExited:(id <NSDraggingInfo>)sender
{
    if (fname == nil) {
        [iconWell setImage:nil];
        [fileField setStringValue:@""];
    }
    else {
        [self displayFile:fname];
    }
}

- (BOOL)performDragOperation:(id <NSDraggingInfo>)sender
{
    NSFileManager *fm = [NSFileManager defaultManager];
    NSWorkspace *wk = [NSWorkspace sharedWorkspace];
    NSDictionary *dict;
    
    if(fname != nil) {
    [fname release];
    }
    fname = [[fileField stringValue] retain];

    dict = [fm fileAttributesAtPath:fname traverseLink:YES];
    
    // if fname is directory and is not file package
    if ([[dict objectForKey:@"NSFileType"] isEqualToString:@"NSFileTypeDirectory"] && ![wk isFilePackageAtPath:fname]) {
        [subCheck setEnabled:YES];
    }
    else {
        [subCheck setEnabled:NO];
    }
        
    // enable subCheck
    return YES;
}
@end
