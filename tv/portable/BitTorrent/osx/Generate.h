/* Generate */

#import <Cocoa/Cocoa.h>
#import <python2.3/Python.h>
#import "BTCallbacks.h"

@interface Generate : NSObject <MetaGenerateCallbacks>
{
    IBOutlet id fileField;
    IBOutlet id gWindow;
    IBOutlet id announce;
    IBOutlet id iconWell;
    IBOutlet id gButton;
    IBOutlet id progressMeter;
    IBOutlet id subCheck;
    NSString *fname;
    PyObject *endflag;
    BOOL done;
}
- (IBAction)generate:(id)sender;
- (void)open;
- (IBAction)cancel:(id)sender;
- (void)displayFile:(NSString *)f;
- (void)savePanelDidEnd:(NSWindow *)sheet returnCode:(int)returnCode contextInfo:(void  *)contextInfo;
// drag protocol
- (NSDragOperation)draggingEntered:(id <NSDraggingInfo>)sender;
- (void)draggingExited:(id <NSDraggingInfo>)sender;
- (BOOL)performDragOperation:(id <NSDraggingInfo>)sender;
- (void)progress:(float)val;
- (void)progressFname:(NSString *)val;
- (void)prepareGenerateSaveFile:(NSString *)f;

@end
