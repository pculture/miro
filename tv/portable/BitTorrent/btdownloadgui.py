#!/usr/bin/env python

# Written by Bram Cohen and Myers Carpenter
# see LICENSE.txt for license information

from sys import argv
from BitTorrent import version
from BitTorrent.download import download
from btdownloadheadless import print_spew
from threading import Event, Thread
from os.path import join, split, exists
from os import getcwd
from wxPython.wx import *
from time import strftime, time
from webbrowser import open_new
from traceback import print_exc

def hours(n):
    if n == -1:
        return '<unknown>'
    if n == 0:
        return 'complete!'
    n = int(n)
    h, r = divmod(n, 60 * 60)
    m, sec = divmod(r, 60)
    if h > 1000000:
        return '<unknown>'
    if h > 0:
        return '%d hour %02d min %02d sec' % (h, m, sec)
    else:
        return '%d min %02d sec' % (m, sec)

wxEVT_INVOKE = wxNewEventType()

def EVT_INVOKE(win, func):
    win.Connect(-1, -1, wxEVT_INVOKE, func)

class InvokeEvent(wxPyEvent):
    def __init__(self):
        wxPyEvent.__init__(self)
        self.SetEventType(wxEVT_INVOKE)

class DownloadInfoFrame:
    def __init__(self, flag):
        frame = wxFrame(None, -1, 'BitTorrent ' + version + ' download', size = wxSize(400, 250))
        self.frame = frame
        self.flag = flag
        self.uiflag = Event()
        self.fin = False
        self.last_update_time = 0
        self.showing_error = False
        self.event = InvokeEvent()
        self.funclist = []

        panel = wxPanel(frame, -1)
        colSizer = wxFlexGridSizer(cols = 1, vgap = 3)

        fnsizer = wxBoxSizer(wxHORIZONTAL)

        self.fileNameText = wxStaticText(panel, -1, '', style = wxALIGN_LEFT)
        fnsizer.Add(self.fileNameText, 1, wxALIGN_BOTTOM)
        self.aboutText = wxStaticText(panel, -1, 'about', style = wxALIGN_RIGHT)
        self.aboutText.SetForegroundColour('Blue')
        self.aboutText.SetFont(wxFont(14, wxNORMAL, wxNORMAL, wxNORMAL, True))
        fnsizer.Add(self.aboutText, 0, wxEXPAND)
        colSizer.Add(fnsizer, 0, wxEXPAND)

        self.gauge = wxGauge(panel, -1, range = 1000, style = wxGA_SMOOTH)
        colSizer.Add(self.gauge, 0, wxEXPAND)

        gridSizer = wxFlexGridSizer(cols = 2, vgap = 3, hgap = 8)
        
        gridSizer.Add(wxStaticText(panel, -1, 'Estimated time left:'))
        self.timeEstText = wxStaticText(panel, -1, '')
        gridSizer.Add(self.timeEstText, 0, wxEXPAND)

        gridSizer.Add(wxStaticText(panel, -1, 'Download to:'))
        self.fileDestText = wxStaticText(panel, -1, '')
        gridSizer.Add(self.fileDestText, 0, wxEXPAND)
        
        gridSizer.AddGrowableCol(1)

        rategridSizer = wxFlexGridSizer(cols = 4, vgap = 3, hgap = 8)

        rategridSizer.Add(wxStaticText(panel, -1, 'Download rate:'))
        self.downRateText = wxStaticText(panel, -1, '')
        rategridSizer.Add(self.downRateText, 0, wxEXPAND)

        rategridSizer.Add(wxStaticText(panel, -1, 'Downloaded:'))
        self.downTotalText = wxStaticText(panel, -1, '')
        rategridSizer.Add(self.downTotalText, 0, wxEXPAND)
        
        rategridSizer.Add(wxStaticText(panel, -1, 'Upload rate:'))
        self.upRateText = wxStaticText(panel, -1, '')
        rategridSizer.Add(self.upRateText, 0, wxEXPAND)
        
        
        rategridSizer.Add(wxStaticText(panel, -1, 'Uploaded:'))
        self.upTotalText = wxStaticText(panel, -1, '')
        rategridSizer.Add(self.upTotalText, 0, wxEXPAND)
       
        rategridSizer.AddGrowableCol(1)
        rategridSizer.AddGrowableCol(3)

        
        colSizer.Add(gridSizer, 0, wxEXPAND)
        colSizer.Add(rategridSizer, 0, wxEXPAND)
        colSizer.Add(50, 50, 0, wxEXPAND)
        self.cancelButton = wxButton(panel, -1, 'Cancel')
        colSizer.Add(self.cancelButton, 0, wxALIGN_CENTER)
        colSizer.AddGrowableCol(0)
        colSizer.AddGrowableRow(3)

        border = wxBoxSizer(wxHORIZONTAL)
        border.Add(colSizer, 1, wxEXPAND | wxALL, 4)
        panel.SetSizer(border)
        panel.SetAutoLayout(True)
        
        EVT_LEFT_DOWN(self.aboutText, self.donate)
        EVT_CLOSE(frame, self.done)
        EVT_BUTTON(frame, self.cancelButton.GetId(), self.done)
        EVT_INVOKE(frame, self.onInvoke)
        self.frame.SetIcon(wxIcon(join(split(argv[0])[0], 'bittorrent.ico'), wxBITMAP_TYPE_ICO))
        self.frame.Show()

    def donate(self, event):
        Thread(target = self.donate2).start()

    def donate2(self):
        open_new('http://bitconjurer.org/BitTorrent/donate.html')

    def onInvoke(self, event):
        while not self.uiflag.isSet() and self.funclist:
            func, args, kwargs = self.funclist.pop(0)
            apply(func, args, kwargs)

    def invokeLater(self, func, args = [], kwargs = {}):
        if not self.uiflag.isSet():
            self.funclist.append((func, args, kwargs))
            if len(self.funclist) == 1:
                wxPostEvent(self.frame, self.event)

    def updateStatus(self, d):
        if (self.last_update_time + 0.1 < time() and not self.showing_error) or d.get('fractionDone') in (0.0, 1.0) or d.has_key('activity'):
            self.invokeLater(self.onUpdateStatus, [d])

    def onUpdateStatus(self, d):
        try:
            if d.has_key('spew'):
                print_spew(d['spew'])
            activity = d.get('activity')
            fractionDone = d.get('fractionDone')
            timeEst = d.get('timeEst')
            downRate = d.get('downRate')
            upRate = d.get('upRate')
            downTotal = d.get('downTotal')
            upTotal = d.get('upTotal')
            if activity is not None and not self.fin:
                self.timeEstText.SetLabel(activity)
            if fractionDone is not None and not self.fin:
                self.gauge.SetValue(int(fractionDone * 1000))
                self.frame.SetTitle('%d%% %s - BitTorrent %s' % (int(fractionDone*100), self.filename, version))
            if timeEst is not None:
                self.timeEstText.SetLabel(hours(timeEst))
            if downRate is not None:
                self.downRateText.SetLabel('%.0f KiB/s' % (float(downRate) / (1 << 10)))
            if upRate is not None:
                self.upRateText.SetLabel('%.0f KiB/s' % (float(upRate) / (1 << 10)))
            if downTotal is not None:
                self.downTotalText.SetLabel('%.1f M' % (downTotal))
            if upTotal is not None:
                self.upTotalText.SetLabel('%.1f M' % (upTotal))
            self.last_update_time = time()
        except:
            print_exc()

    def finished(self):
        self.fin = True
        self.invokeLater(self.onFinishEvent)

    def failed(self):
        self.fin = True
        self.invokeLater(self.onFailEvent)

    def error(self, errormsg):
        if not self.showing_error:
            self.invokeLater(self.onErrorEvent, [errormsg])

    def onFinishEvent(self):
        self.timeEstText.SetLabel('Download Succeeded!')
        self.cancelButton.SetLabel('Close')
        self.gauge.SetValue(1000)
        self.frame.SetTitle('%s - Upload - BitTorrent %s' % (self.filename, version))
        self.downRateText.SetLabel('')

    def onFailEvent(self):
        self.timeEstText.SetLabel('Failed!')
        self.cancelButton.SetLabel('Close')
        self.gauge.SetValue(0)
        self.downRateText.SetLabel('')

    def onErrorEvent(self, errormsg):
        self.showing_error = True
        dlg = wxMessageDialog(self.frame, message = errormsg, 
            caption = 'Download Error', style = wxOK | wxICON_ERROR)
        dlg.Fit()
        dlg.Center()
        dlg.ShowModal()
        self.showing_error = False

    def chooseFile(self, default, size, saveas, dir):
        f = Event()
        bucket = [None]
        self.invokeLater(self.onChooseFile, [default, bucket, f, size, dir, saveas])
        f.wait()
        return bucket[0]
    
    def onChooseFile(self, default, bucket, f, size, dir, saveas):
        if not saveas:
            if dir:
                dl = wxDirDialog(self.frame, 'Choose a directory to save to, pick a partial download to resume', 
                    join(getcwd(), default), style = wxDD_DEFAULT_STYLE | wxDD_NEW_DIR_BUTTON)
            else:
                dl = wxFileDialog(self.frame, 'Choose file to save as, pick a partial download to resume', '', default, '*', wxSAVE)
            if dl.ShowModal() != wxID_OK:
                self.done(None)
                f.set()
                return
            saveas = dl.GetPath()
        bucket[0] = saveas
        self.fileNameText.SetLabel('%s (%.1f MB)' % (default, float(size) / (1 << 20)))
        self.timeEstText.SetLabel('Starting up...')
        self.fileDestText.SetLabel(saveas)
        self.filename = default
        self.frame.SetTitle(default + '- BitTorrent ' + version)
        f.set()

    def newpath(self, path):
        self.fileDestText.SetLabel(path)

    def done(self, event):
        self.uiflag.set()
        self.flag.set()
        self.frame.Destroy()

class btWxApp(wxApp):
    def __init__(self, x, params):
        self.params = params
        wxApp.__init__(self, x)

    def OnInit(self):
        doneflag = Event()
        d = DownloadInfoFrame(doneflag)
        self.SetTopWindow(d.frame)
        thread = Thread(target = next, args = [self.params, d, doneflag])
        thread.setDaemon(False)
        thread.start()
        return 1

def run(params):
    try:
        app = btWxApp(0, params)
        app.MainLoop()
    except:
        print_exc()

def next(params, d, doneflag):
    try:
        p = join(split(argv[0])[0], 'donated')
        if not exists(p) and long(time()) % 3 == 0:
            open_new('http://bitconjurer.org/BitTorrent/donate.html')
            dlg = wxMessageDialog(d.frame, 'BitTorrent is Donation supported software. ' + 
                'Please go to the donation page (which should be appearing for you now) and make a donation from there. ' + 
                'Or you can click no and donate later.\n\nHave you made a donation yet?',
                'Donate!', wxYES_NO | wxICON_INFORMATION | wxNO_DEFAULT)
            if dlg.ShowModal() == wxID_YES:
                dlg.Destroy()
                dlg = wxMessageDialog(d.frame, 'Thanks for your donation! You will no longer be shown donation requests.\n\n' + 
                    "If you haven't actually made a donation and are feeling guilty (as you should!) you can always get to " + 
                    "the donation page by clicking the 'about' link in the upper-right corner of the main BitTorrent window and " + 
                    'donating from there.', 'Thanks!', wxOK)
                dlg.ShowModal()
                dlg.Destroy()
                try:
                    open(p, 'wb').close()
                except IOError, e:
                    dlg = wxMessageDialog(d.frame, "Sorry, but I couldn't set the flag to not ask you for donations in the future - " + str(e),
                        'Sorry!', wxOK | wxICON_ERROR)
                    dlg.ShowModal()
                    dlg.Destroy()
            else:
                dlg.Destroy()
        download(params, d.chooseFile, d.updateStatus, d.finished, d.error, doneflag, 100, d.newpath)
        if not d.fin:
            d.failed()
    except:
        print_exc()

if __name__ == '__main__':
    run(argv[1:])
