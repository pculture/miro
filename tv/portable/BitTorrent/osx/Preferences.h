/* Preferences */

#import <Cocoa/Cocoa.h>

#define MINPORT @"minport"
#define MAXPORT @"maxport"
#define IP @"ip"

#define MINPORT_DEFAULT 6881
#define MAXPORT_DEFAULT 6889
#define IP_DEFAULT @""

@interface Preferences : NSWindowController
{
    IBOutlet id ip;
    IBOutlet id maxport;
    IBOutlet id minport;
}
- (IBAction)cancel:(id)sender;
- (IBAction)loadFactory:(id)sender;
- (IBAction)save:(id)sender;
- (IBAction)resetFields:(id)sender;

- (void)windowDidBecomeKey:(NSNotification *)aNotification;
@end
