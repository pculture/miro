//
//  ICHelper.h
//  BitTorrent
//
//  Created by Dr. Burris T. Ewell on Sat Jul 27 2002.
//  Copyright (c) 2001 __MyCompanyName__. All rights reserved.
//

#import <Foundation/Foundation.h>
#import <Carbon/Carbon.h>


@interface ICHelper : NSObject {
    ICInstance ici;
}
- (id) installICHandler:sender;
@end
