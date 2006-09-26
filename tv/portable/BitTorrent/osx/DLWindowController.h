/* DLWindowController */

#import <Cocoa/Cocoa.h>
#import <python2.3/Python.h>
#import "BTCallbacks.h"

@interface DLWindowController : NSWindowController <BTCallbacks>
{
    IBOutlet id dlRate;
    IBOutlet id lastError;
    IBOutlet id file;
    IBOutlet id percentCompleted;
    IBOutlet id progressBar;
    IBOutlet id timeRemaining;
    IBOutlet id ulRate;
    IBOutlet id max_upload_rate;
    IBOutlet id max_uploads;
    IBOutlet id peerStat;
    IBOutlet id ulTotal;
    IBOutlet id dlTotal;

    NSString *timeEst;
    NSString *savepath;
    float frac;
    PyObject *flag, *chooseflag;
    PyObject *rateFunc, *maxUploadsFunc, *addPeerFunc;
    double totalsize;
    NSConnection *conn;
    NSToolbar *toolBar;
    NSNetService *publisher;
    NSNetServiceBrowser *browser;
    int done;
}
- (IBAction)cancelDl:(id)sender;
- (id)init;
- (void)finished;
- (void)error:(NSString *)str;
- (void)display:(NSData *)dict;
- (void)pathUpdated:(NSString *)newPath;
- (void)chooseFile:(NSString *)defaultFile size:(double)size isDirectory:(int)dir;
- (void)paramFunc:(NSData *)paramDict;
- (NSString *)savePath;
- (void)dlExited;
- (PyObject *)rateFunc;
- (PyObject *)maxUploadsFunc;
- (void)setFlag:(PyObject *)nflag;
- (void)setChooseFlag:(PyObject *)nflag;
- (void)setConnection:(NSConnection *)nc;
- (void)dealloc;
- (IBAction)takeMaxUploadRateFrom:(id)sender;
- (IBAction)takeMaxUploadsFrom:(id)sender;
- (void)awakeFromNib;

- (void)savePanelDidEnd:(NSSavePanel *)sheet returnCode:(int)returnCode contextInfo:(void  *)contextInfo;
- (void)openPanelDidEnd:(NSOpenPanel *)sheet returnCode:(int)returnCode contextInfo:(void  *)contextInfo;

- (id)validRequestorForSendType:(NSString *)sendType returnType:(NSString *)returnType;

// toolbar delegate methods
- (NSArray *)toolbarAllowedItemIdentifiers:(NSToolbar*)toolbar;
- (NSArray *)toolbarDefaultItemIdentifiers:(NSToolbar*)toolbar;

// rendezvous
- (void)netService:(NSNetService *)sender didNotPublish:(NSDictionary *)errorDict;
- (void)netServiceWillPublish:(NSNetService *)sender;
- (void)netServiceBrowser:(NSNetServiceBrowser *)aNetServiceBrowser didFindService:(NSNetService *)aNetService moreComing:(BOOL)moreComing;

@end
