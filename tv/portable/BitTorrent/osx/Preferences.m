#import "Preferences.h"

@implementation Preferences

- init
{
    NSUserDefaults *defaults; 
    NSMutableDictionary *appDefaults;

    [super init];
    defaults = [NSUserDefaults standardUserDefaults];
    appDefaults = [NSMutableDictionary dictionaryWithObject:IP_DEFAULT forKey:IP];
    [appDefaults setObject:[NSNumber numberWithInt:MINPORT_DEFAULT] forKey:MINPORT];
    [appDefaults setObject:[NSNumber numberWithInt:MAXPORT_DEFAULT] forKey:MAXPORT];
    [defaults registerDefaults:appDefaults];
    return self;
}

- (void)windowDidBecomeKey:(NSNotification *)aNotification
{
    [self resetFields:self];
}

- (IBAction)cancel:(id)sender
{
    [self resetFields:self];
    [[self window] close];
}

- (IBAction)resetFields:(id)sender
{
    NSUserDefaults *defaults; 
    
    defaults = [NSUserDefaults standardUserDefaults];
    [ip setStringValue:[defaults objectForKey:IP]];
    [minport setStringValue:[defaults objectForKey:MINPORT]];
    [maxport setStringValue:[defaults objectForKey:MAXPORT]];
}

- (IBAction)loadFactory:(id)sender
{
    [ip setStringValue:IP_DEFAULT];
    [minport setIntValue:MINPORT_DEFAULT];
    [maxport setIntValue:MAXPORT_DEFAULT];
}

- (IBAction)save:(id)sender
{
    NSUserDefaults *defaults; 
    
    defaults = [NSUserDefaults standardUserDefaults];
    [defaults setObject:[ip stringValue] forKey:IP];
    [defaults setObject:[minport stringValue] forKey:MINPORT];
    [defaults setObject:[maxport stringValue] forKey:MAXPORT];
    [[self window] close];
}

@end
