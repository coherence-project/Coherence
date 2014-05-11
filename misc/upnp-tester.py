#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2008, Frank Scholz <coherence@beebits.net>

# upnp-tester.py
#
# very basic atm
#
# provides these functions:
#
# list           - display all devices
# extract <uuid> - extract device and service xml files and put them in a
#                  /tmp/<uuid> directory
# send <uuid>    - pack the before extracted xml files in a tar.gz and
#                  send them via email to the Coherence googlemail account
#

import os
from sets import Set

from twisted.internet import stdio
from twisted.protocols import basic
from twisted.internet import protocol

try:
    from twisted.mail import smtp

    from twisted.names import client as namesclient
    from twisted.names import dns

    import StringIO


    class SMTPClient(smtp.ESMTPClient):

        """ build an email message and send it to our googlemail account
        """

        def __init__(self, mail_from, mail_to, mail_subject, mail_file, *args, **kwargs):
            smtp.ESMTPClient.__init__(self, *args, **kwargs)
            self.mailFrom = mail_from
            self.mailTo = mail_to
            self.mailSubject = mail_subject
            self.mail_file = mail_file
            self.mail_from = mail_from

        def getMailFrom(self):
            result = self.mailFrom
            self.mailFrom = None
            return result

        def getMailTo(self):
            return [self.mailTo]

        def getMailData(self):
            from email.mime.application import MIMEApplication
            from email.mime.multipart import MIMEMultipart

            msg = MIMEMultipart()
            msg['Subject'] = self.mailSubject
            msg['From'] = self.mail_from
            msg['To'] = self.mailTo
            fp = open(self.mail_file, 'rb')
            tar = MIMEApplication(fp.read(), 'x-tar')
            fp.close()
            tar.add_header('Content-Disposition', 'attachment', filename=os.path.basename(self.mail_file))
            msg.attach(tar)
            return StringIO.StringIO(msg.as_string())

        def sentMail(self, code, resp, numOk, addresses, log):
            print 'Sent', numOk, 'messages'


    class SMTPClientFactory(protocol.ClientFactory):
        protocol = SMTPClient

        def __init__(self, mail_from, mail_to, mail_subject, mail_file, *args, **kwargs):
            self.mail_from = mail_from
            self.mail_to = mail_to
            self.mail_subject = mail_subject
            self.mail_file = mail_file

        def buildProtocol(self, addr):
            return self.protocol(self.mail_from, self.mail_to,
                                 self.mail_subject, self.mail_file,
                                 secret=None, identity='localhost')

except ImportError:
    pass

from twisted.internet import reactor, defer
from twisted.web import client

from coherence.base import Coherence


class UI(basic.LineReceiver):
    from os import linesep as delimiter

    def connectionMade(self):
        self.print_prompt()

    def lineReceived(self, line):
        args = line.strip().split()
        if args:
            cmd = args[0].lower()
            if hasattr(self, 'cmd_%s' % cmd):
                getattr(self, 'cmd_%s' % (cmd))(args[1:])
            elif cmd == "?":
                self.cmd_help(args[1:])
            else:
                self.transport.write("""Unknown command '%s'\n""" % (cmd))
        self.print_prompt()

    def cmd_help(self, args):
        "help -- show help"
        methods = Set([getattr(self, x) for x in dir(self) if x[:4] == "cmd_"])
        self.transport.write("Commands:\n")
        for method in methods:
            if hasattr(method, '__doc__'):
                self.transport.write("%s\n" % (method.__doc__))

    def cmd_list(self, args):
        "list -- list devices"
        self.transport.write("Devices:\n")
        for d in self.coherence.get_devices():
            self.transport.write(str("%s %s [%s/%s/%s]\n" % (d.friendly_name, ':'.join(d.device_type.split(':')[3:5]), d.st, d.usn.split(':')[1], d.host)))

    def cmd_extract(self, args):
        "extract <uuid> -- download xml files from device"
        device = self.coherence.get_device_with_id(args[0])
        if device == None:
            self.transport.write("device %s not found - aborting\n" % args[0])
        else:
            self.transport.write(str("extracting from %s @ %s\n" % (device.friendly_name, device.host)))
            try:
                l = []

                def device_extract(workdevice, path):
                    tmp_dir = os.path.join(path, workdevice.get_uuid())
                    os.mkdir(tmp_dir)
                    d = client.downloadPage(workdevice.get_location(), os.path.join(tmp_dir, 'device-description.xml'))
                    l.append(d)

                    for service in workdevice.services:
                        d = client.downloadPage(service.get_scpd_url(), os.path.join(tmp_dir, '%s-description.xml' % service.service_type.split(':', 3)[3]))
                        l.append(d)


                    for ed in workdevice.devices:
                        device_extract(ed, tmp_dir)

                def finished(result):
                    self.transport.write(str("\nextraction of device %s finished\nfiles have been saved to /tmp/%s\n" % (args[0], args[0])))
                    self.print_prompt()

                device_extract(device, '/tmp')

                dl = defer.DeferredList(l)
                dl.addCallback(finished)
            except Exception, msg:
                self.transport.write(str("problem creating download directory %s\n" % msg))

    def cmd_send(self, args):
        "send <uuid> -- send before extracted xml files to the Coherence home base"
        if os.path.isdir(os.path.join('/tmp', args[0])) == 1:
            cwd = os.getcwd()
            os.chdir('/tmp')
            import tarfile
            tar = tarfile.open(os.path.join('/tmp', args[0] + '.tgz'), "w:gz")
            for file in os.listdir(os.path.join('/tmp', args[0])):
                tar.add(os.path.join(args[0], file))
            tar.close()
            os.chdir(cwd)

            def got_mx(result):
                mx_list = result[0]
                mx_list.sort(lambda x, y: cmp(x.payload.preference, y.payload.preference))
                if len(mx_list) > 0:
                    import posix
                    import pwd
                    import socket
                    reactor.connectTCP(str(mx_list[0].payload.name), 25,
                        SMTPClientFactory('@'.join((pwd.getpwuid(posix.getuid())[0], socket.gethostname())), 'upnp.fingerprint@googlemail.com', 'xml-files', os.path.join('/tmp', args[0] + '.tgz')))

            mx = namesclient.lookupMailExchange('googlemail.com')
            mx.addCallback(got_mx)

    def cmd_quit(self, args):
        "quit -- quits this program"
        reactor.stop()

    cmd_exit = cmd_quit

    def print_prompt(self):
        self.transport.write('>>> ')



if __name__ == '__main__':

    c = Coherence({'logmode': 'none'})
    ui = UI()
    ui.coherence = c

    stdio.StandardIO(ui)

    reactor.run()
