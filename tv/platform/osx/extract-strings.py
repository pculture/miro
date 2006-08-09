from glob import glob
import os
for nib in glob("English.lproj/*.nib"):
    name = os.path.basename (nib)[:-4]
    os.system ("nibtool English.lproj/%s.nib -L -8 > English.lproj/%s.strings" % (name, name))
    
