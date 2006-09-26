#import <python2.3/Python.h>
@protocol Tstate
- (PyThreadState *)tstate;
- (void)setTstate:(PyThreadState *)nstate;
@end
