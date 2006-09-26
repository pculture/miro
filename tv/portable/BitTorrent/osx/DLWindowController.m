#import "DLWindowController.h"
#import "Tstate.h"
#import <DNSServiceDiscovery/DNSServiceDiscovery.h>

@interface RateItem : NSToolbarItem
{
}
- validate;
@end
@implementation RateItem
- validate 
{
    if ([[self target] rateFunc]) {
        [self setEnabled:YES];
    }
    else {
        [self setEnabled:NO];
    }
    return self;
}
@end
@interface MaxUploadsItem : NSToolbarItem
{
}
- validate;
@end
@implementation MaxUploadsItem
- validate 
{
    if ([[self target] maxUploadsFunc]) {
        [self setEnabled:YES];
    }
    else {
        [self setEnabled:NO];
    }
    return self;
}
@end

@implementation DLWindowController

#define LASTDIR @"LastSaveDir"

- (id)init
{ 
    NSUserDefaults *defaults; 
    NSMutableDictionary *appDefaults;
    
    [super init];
    timeEst = [@"" retain];
    conn = nil;
    done = 0;
    
    defaults = [NSUserDefaults standardUserDefaults];
    appDefaults = [NSMutableDictionary
    dictionaryWithObject:NSHomeDirectory() forKey:LASTDIR];
    [defaults registerDefaults:appDefaults];

    toolBar = [[NSToolbar alloc] initWithIdentifier:@"DLWindow"];
    [toolBar setDelegate:self];
    [toolBar setVisible:NO];
    return self;
}

- (void)awakeFromNib
{
    [[self window] setToolbar:toolBar];
}

- (void)windowWillClose:(NSNotification *)aNotification
{
    [self cancelDl:self];
}

- (void)windowDidClose:(NSNotification *)aNotification
{
    [self autorelease];
}
- (IBAction)cancelDl:(id)sender
{
    [publisher stop];
    [browser stop];
    PyEval_RestoreThread([[NSApp delegate] tstate]);
    PyObject_CallMethod(flag, "set", NULL);
    [[NSApp delegate] setTstate:PyEval_SaveThread()];
}

- (void)setFlag:(PyObject *)nflag
{
    flag = nflag;
    Py_INCREF(flag);
}
- (void)setChooseFlag:(PyObject *)nflag
{
    chooseflag = nflag;
    Py_INCREF(chooseflag);
}

- (void)setConnection:(NSConnection *)nc
{
    if(conn)
    {
    [conn release];
    }
    conn = [nc retain];
}

- (NSString *)hours:(long) n
{
    long h, r, m, sec;
    
    if (n == -1)
    return @"<unknown>";
    if (n == 0)
    return @"Complete!";
    h = n / (60 * 60);
    r = n % (60 * 60);
    
    m = r / 60;
    sec = r % 60;
    
    if (h > 1000000)
    return @"<unknown>";
    if (h > 0)
    return [NSString stringWithFormat:@"%d hour(s) %2d min(s) %2d sec(s)", h, m, sec];
    else
    return [NSString stringWithFormat:@"%2d min(s) %2d sec(s)", m, sec]; 
}

- (void)savePanelDidEnd:(NSSavePanel *)sheet returnCode:(int)returnCode contextInfo:(void  *)contextInfo
{
    if(returnCode == NSOKButton) {
        [file setStringValue:[NSString stringWithFormat:NSLocalizedString(@"(%1.1f MiB) %@ ", @"size and filename for dl window tite") , totalsize, [sheet filename]]];
        [[self window] setTitleWithRepresentedFilename:[sheet filename]];
        [[NSUserDefaults standardUserDefaults] setObject:[sheet directory] forKey:LASTDIR];
        savepath = [[sheet filename] retain];
    }
    else {
        // user cancelled
        [[self window] performClose:self];
    }
    PyEval_RestoreThread([[NSApp delegate] tstate]);
    PyObject_CallMethod(chooseflag, "set", NULL);
    [[NSApp delegate] setTstate:PyEval_SaveThread()];
}

- (void)openPanelDidEnd:(NSOpenPanel *)sheet returnCode:(int)returnCode contextInfo:(void  *)contextInfo
{
    if(returnCode == NSOKButton) {
        [file setStringValue:[NSString stringWithFormat:NSLocalizedString(@"(%1.1f MiB) %@ ", @"size and filename for dl window tite") , totalsize, [sheet filename]]];
        [[self window] setTitleWithRepresentedFilename:[sheet filename]];
        [[NSUserDefaults standardUserDefaults] setObject:[sheet directory] forKey:LASTDIR];
        savepath = [[sheet filename] retain];
    }
    else {
        // user cancelled
        [[self window] performClose:self];
    }
    PyEval_RestoreThread([[NSApp delegate] tstate]);
    PyObject_CallMethod(chooseflag, "set", NULL);
    [[NSApp delegate] setTstate:PyEval_SaveThread()];

}

- (NSString *)savePath
{
    return savepath;
}
- (void)chooseFile:(NSString *)defaultFile size:(double)size isDirectory:(int)dir{
    id panel;
    
    totalsize = size;
    [[self window] setTitleWithRepresentedFilename:defaultFile];
    if(!dir) {
        panel = [NSSavePanel savePanel];
        [panel setTitle:NSLocalizedString(@"Save, choose an existing file to resume.", @"save instructions")];
        [panel beginSheetForDirectory:[[NSUserDefaults standardUserDefaults] objectForKey:LASTDIR] file:defaultFile modalForWindow:[self window] modalDelegate:self didEndSelector:@selector(savePanelDidEnd:returnCode:contextInfo:) contextInfo:nil];
    }
    else {
        panel = [NSOpenPanel openPanel];
        [panel setCanChooseFiles:YES];
        [panel setCanChooseDirectories:YES];
        [panel setTitle:defaultFile];
        [panel setPrompt:NSLocalizedString(@"Save", @"save directory prompt")];
        [panel beginSheetForDirectory:[[NSUserDefaults standardUserDefaults] objectForKey:LASTDIR] file:defaultFile modalForWindow:[self window] modalDelegate:self didEndSelector:@selector(openPanelDidEnd:returnCode:contextInfo:) contextInfo:nil];
    }
}

- (void)pathUpdated:(NSString *)newPath
{
    [file setStringValue:[NSString stringWithFormat:NSLocalizedString(@"(%1.1f MiB) %@ ", @"size and filename for dl window tite") , totalsize, newPath]];
    [[self window] setTitleWithRepresentedFilename:newPath];
    [savepath release];
    savepath = [newPath retain];
}

- (void)display:(NSData *)dict
{
    NSString *str, *activity;
    PyObject *spew, *d, *x;
    long est;
    
    [dict getBytes:&d];
    
    PyEval_RestoreThread([[NSApp delegate] tstate]);

    activity = nil;
    if(!done) {   
        if (x = PyDict_GetItemString(d, "activity")) {
            activity = [NSString stringWithCString:PyString_AsString(x)];
        }
        if (x = PyDict_GetItemString(d, "fractionDone")) {
            frac = PyFloat_AsDouble(x);
        }
        // format dict timeEst here and put in ivar timeEst
        if (x = PyDict_GetItemString(d, "timeEst")) {
            est = PyInt_AsLong(x);
            if(est > 0) {
                [timeEst release];
                timeEst = [[self hours:est] retain];
            }
        }
        if(activity && ![activity isEqualToString:@""]) {
            [timeEst release];
            timeEst = [activity retain];
        }
        
        str = [NSString stringWithFormat:NSLocalizedString(@"%2.1f%%", @"percent dl completed"), frac * 100];
    
        [percentCompleted setStringValue:str];
        [progressBar setDoubleValue:frac];
        [timeRemaining setStringValue:timeEst];
    }

    if (x = PyDict_GetItemString(d, "downRate")) {
        [dlRate setStringValue:[NSString stringWithFormat:NSLocalizedString(@"%2.1f KiB/s",@"transfer rate"), PyFloat_AsDouble(x) / 1024]];
    }
    if (x = PyDict_GetItemString(d, "downTotal")) {
        [dlTotal setStringValue:[NSString stringWithFormat:NSLocalizedString(@"%2.1f MiB",@"transfer total"), PyFloat_AsDouble(x)]];
    }

    if (x = PyDict_GetItemString(d, "upRate")) {
        [ulRate setStringValue:[NSString stringWithFormat:NSLocalizedString(@"%2.1f KiB/s", @"transfer rate"), PyFloat_AsDouble(x) / 1024]];
    }
    if (x = PyDict_GetItemString(d, "upTotal")) {
        [ulTotal setStringValue:[NSString stringWithFormat:NSLocalizedString(@"%2.1f MiB",@"transfer total"), PyFloat_AsDouble(x)]];
    }
    
    if (spew = PyDict_GetItemString(d, "spew")){
        [peerStat setStringValue:[NSString stringWithFormat:NSLocalizedString(@"Connected to %d peers.", @"num connected peers info string"), PyList_Size(spew)]];
    }
    Py_DECREF(d);
    [[NSApp delegate] setTstate:PyEval_SaveThread()];
}

- (void)paramFunc:(NSData *)paramDict
{
    PyObject *dict, *pid, *ihash, *mm, *md, *he;
    char *peer_id, *info_hash;
    int listen_port;
    
    PyEval_RestoreThread([[NSApp delegate] tstate]);
    [paramDict getBytes:&dict];
    rateFunc = PyDict_GetItemString(dict, "max_upload_rate");
    if (rateFunc) {
        Py_INCREF(rateFunc);
    }
    maxUploadsFunc = PyDict_GetItemString(dict, "max_uploads");
    if (maxUploadsFunc) {
        Py_INCREF(maxUploadsFunc);
    }
    addPeerFunc = PyDict_GetItemString(dict, "start_connection");
    if (addPeerFunc) {
        Py_INCREF(addPeerFunc);
    }

    
    // rendezvous 
    
    mm = PyImport_ImportModule("__main__");
    md = PyModule_GetDict(mm);
    he = PyDict_GetItemString(md, "b2a_hex");

    listen_port = PyInt_AsLong(PyDict_GetItemString(dict, "listen_port"));
    pid = PyObject_CallFunction(he, "O", PyDict_GetItemString(dict, "peer_id"));
    peer_id = PyString_AsString(pid);
    ihash = PyObject_CallFunction(he, "O", PyDict_GetItemString(dict, "info_hash"));
    info_hash = PyString_AsString(ihash);
    
    if (listen_port && peer_id && info_hash) {
        publisher = [[NSNetService alloc] initWithDomain:@""
                                            type:[NSString stringWithFormat:@"_BitTorrent-%s._tcp", info_hash]
                                        name:[NSString stringWithCString:peer_id] port:listen_port];
        if(publisher) {
            [publisher setDelegate:self];
            [publisher publish];
        }
        
        browser = [[NSNetServiceBrowser alloc] init];
        if(browser) {
            [browser setDelegate:self];
            [browser searchForServicesOfType:[NSString stringWithFormat:@"_BitTorrent-%s._tcp", info_hash] inDomain:@""];
        }
    Py_DECREF(mm);
    Py_DECREF(pid);
    Py_DECREF(ihash);
    }


    Py_DECREF(dict);
    [[NSApp delegate] setTstate:PyEval_SaveThread()];
}

- (void)finished
{
    done = 1;
    [timeEst release];
    timeEst = [NSLocalizedString(@"Download Succeeded.", @"download completed successfully") retain];
    [progressBar setDoubleValue:100.0];
    [timeRemaining setStringValue:timeEst];
    [dlRate setStringValue:@""];
    [percentCompleted setStringValue:NSLocalizedString(@"100%", @"one hundred percent")];
}

- (void)dlExited
{
    if(!done) {
        [progressBar setDoubleValue:0.0];
        [timeRemaining setStringValue:NSLocalizedString(@"Download Failed!", @"download failed")];
        [dlRate setStringValue:@""];
        [ulRate setStringValue:@""];
        [percentCompleted setStringValue:@""];
        if(publisher) {
            [publisher stop];
        }
    }
}

- (void)error:(NSString *)str
{
    [lastError setStringValue:str];
}

- (void)dealloc
{
    [conn release];
    conn = nil;
    [timeEst release];
    timeEst = nil;
    PyEval_RestoreThread([[NSApp delegate] tstate]);
    if (flag) {
        Py_DECREF(flag);
        flag = nil;
    }
    if (chooseflag) {
        Py_DECREF(chooseflag);
        chooseflag = nil;
    }
    if(rateFunc) {
        Py_DECREF(rateFunc);
        rateFunc = nil;
    }
    if(publisher) {
        [publisher release];
    }
    if(browser) {
        [browser release];
    }
    [[NSApp delegate] setTstate:PyEval_SaveThread()];
    [super dealloc];
}

// Services stuff...
- (id)validRequestorForSendType:(NSString *)sendType returnType:(NSString *)returnType {
    if (returnType == nil && ([sendType isEqualToString:NSFilenamesPboardType] ||[sendType isEqualToString:NSStringPboardType])) {
        return self;
    }
    return nil;
}

- (BOOL)writeSelectionToPasteboard:(NSPasteboard *)pboard types:(NSArray *)types
{

    if ([types containsObject:NSFilenamesPboardType] == NO && [types containsObject:NSStringPboardType] == NO) {
        return NO;
    }

    [pboard declareTypes:[NSArray arrayWithObjects:NSStringPboardType, nil] owner:nil];
    [pboard setPropertyList:[NSArray arrayWithObjects:savepath, nil] forType:NSFilenamesPboardType];
    [pboard setString:savepath forType:NSStringPboardType];
    return YES;
}

- (PyObject *)rateFunc
{
    return rateFunc;
}

- (PyObject *) maxUploadsFunc
{
    return maxUploadsFunc;
}
- (IBAction)takeMaxUploadRateFrom:(id)sender
{
    PyObject *args;
    [sender setIntValue:[sender intValue]];
    PyEval_RestoreThread([[NSApp delegate] tstate]);
    args = Py_BuildValue("(i)", [sender intValue] * 1000);
    PyObject_CallObject(rateFunc, args);
    Py_DECREF(args);
    [[NSApp delegate] setTstate:PyEval_SaveThread()];    
}
- (IBAction)takeMaxUploadsFrom:(id)sender
{
    PyObject *args;
    int val = [sender intValue];
    if (val < 2) {
        val = 2;
    }
    [sender setIntValue:val];
    PyEval_RestoreThread([[NSApp delegate] tstate]);
    args = Py_BuildValue("(i)", val);
    PyObject_CallObject(maxUploadsFunc, args);
    Py_DECREF(args);
    [[NSApp delegate] setTstate:PyEval_SaveThread()];    
}


// toolbar delegate methods

- (NSArray *)toolbarAllowedItemIdentifiers:(NSToolbar*)toolbar
{
    return (NSArray *)[NSArray arrayWithObjects:@"max_upload_rate", @"max_uploads", nil];
}

- (NSArray *)toolbarDefaultItemIdentifiers:(NSToolbar*)toolbar
{
    return (NSArray *)[NSArray arrayWithObjects:@"max_upload_rate", @"max_uploads", nil];
}

- (NSToolbarItem *)toolbar:(NSToolbar *)toolbar itemForItemIdentifier:(NSString *)itemIdentifier willBeInsertedIntoToolbar:(BOOL)flag
{
    NSToolbarItem *item;
    NSRect rect;
    if ([itemIdentifier isEqualTo:@"max_upload_rate"]) {
        item = [[RateItem alloc] initWithItemIdentifier:@"max_upload_rate"];
        [item setView:max_upload_rate];
        [item setTarget:self];
        [item setAction:@selector(takeMaxUploadRateFrom:)];
        [item setLabel:NSLocalizedString(@"Max UL KiB/s", @"max_upload_rate toolbar label")];
        [item setPaletteLabel:NSLocalizedString(@"Maximum Upload Rate", @"max_upload_rate toolbar palette label")];
        rect = [max_upload_rate frame];
        [item setMinSize:rect.size];
        [item setEnabled:NO];
    }
    else if ([itemIdentifier isEqualTo:@"max_uploads"]) {
        item = [[MaxUploadsItem alloc] initWithItemIdentifier:@"max_uploads"];
        [item setView:max_uploads];
        [item setTarget:self];
        [item setAction:@selector(takeMaxUploadsFrom:)];
        [item setLabel:NSLocalizedString(@"Num Uploads", @"max_uploads toolbar label")];
        [item setPaletteLabel:NSLocalizedString(@"Number of Uploads", @"max_uploads toolbar palette label")];
        rect = [max_uploads frame];
        [item setMinSize:rect.size];
        [item setEnabled:NO];
    }
    
    return item;
}


// rendezvous delegate

- (void)netService:(NSNetService *)sender didNotPublish:(NSDictionary *)errorDict
{
    NSLog(@"Failed to publish...");
}

- (void)netServiceWillPublish:(NSNetService *)sender
{
}

- (void)netServiceBrowser:(NSNetServiceBrowser *)aNetServiceBrowser didFindService:(NSNetService *)peer moreComing:(BOOL)moreComing
{
    [peer setDelegate:self];
    [peer resolve];
}

- (void)netServiceDidResolveAddress:(NSNetService *)peer
{
    struct sockaddr_in *ip, ip_s;
    NSData *a;
    char *str;
    PyObject *mm, *md, *he, *pid;
    NSEnumerator *iter = [[peer addresses] objectEnumerator];

    PyEval_RestoreThread([[NSApp delegate] tstate]);

    mm = PyImport_ImportModule("__main__");
    md = PyModule_GetDict(mm);
    he = PyDict_GetItemString(md, "a2b_hex");

    while ((a = [iter nextObject]) != nil) {
        [a getBytes:&ip_s];
        ip = &ip_s;
        union { uint32_t l; u_char b[4]; } addr = { ip->sin_addr.s_addr };
        union { uint16_t s; u_char b[2]; } port = { ip->sin_port };
        uint16_t PortAsNumber = ((uint16_t)port.b[0]) << 8 | port.b[1];
        str = [[NSString stringWithFormat:@"%d.%d.%d.%d", addr.b[0], addr.b[1], addr.b[2], addr.b[3]] cString];
        pid = PyObject_CallFunction(he, "s", [[peer name] cString]);
        if(pid) {
            PyObject_CallFunction(addPeerFunc, "(si)O", str, PortAsNumber, pid);
            Py_DECREF(pid);
        }
    }
    Py_DECREF(mm);
    [[NSApp delegate] setTstate:PyEval_SaveThread()];
}
@end
