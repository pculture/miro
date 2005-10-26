If you're upgrading from beta 1 or beta 2, and you're on Mac OS X 10.3
(Panther) then you will lose your channel subscriptions when you upgrade, 
because of a mistake we made in the way we store files.

If you want to save your channel subscriptions, just follow these steps:

1) Find the old DTV.app
2) Control-click (or right-click) on it and select "Show Package Contents"
3) Go to Contents > Resources > ${APPDATA}
4) Create a folder /Users/<username>/Library/Application Support/DTV
5) Move all the files in the ${APPDATA} folder to the folder created in step 4
6) If you have a bittorent-dtv folder in your home directory (/Users/<username>/)
   check if it only contains empty folders. If it does you can safely delete it, 
   a new one will be automatically created at the right place the next time you 
   launch DTV. If it contains files, move it to the folder you created in
   step 4
6) Copy the new DTV.app over the old DTV.app
8) Run the new DTV.app

