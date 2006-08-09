from glob import glob
import os
for nib in glob("Resources/English.lproj/*.nib"):
    name = os.path.basename (nib)[:-4]
    os.system ("nibtool Resources/English.lproj/%s.nib -L -8 > Resources/English.lproj/%s.strings" % (name, name))
    
