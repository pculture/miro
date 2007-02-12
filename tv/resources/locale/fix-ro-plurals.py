#!/usr/bin/env python

import os

bad_str = '"Plural-Forms: nplurals=3; plural=((n == 1 ? 0: (((n %\\n"\n"100 > 19) || ((n % 100 == 0) && (n != 0))) ? 2: 1)));\\n"'

good_str = '"Plural-Forms: nplurals=3; plural=((n == 1 ? 0: (((n % 100 > 19) || ((n % 100 == 0) && (n != 0))) ? 2: 1)));\\n"'

ro_path = os.path.normpath(os.path.join(__file__, '..', 'ro.po'))
content = open(ro_path).read()
if bad_str in content:
    print 'fixing ro.po'
    f = open(ro_path, 'wt')
    f.write(content.replace(bad_str, good_str))
    f.close()
