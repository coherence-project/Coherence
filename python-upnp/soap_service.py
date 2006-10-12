# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2005, Tim Potter <tpot@samba.org>
# Copyright 2006 John-Mark Gurney <gurney_j@resnet.uroegon.edu>

from twisted.web import soap
from twisted.python import log

import SOAPpy

class errorCode(Exception):
	def __init__(self, status):
		self.status = status

class UPnPPublisher(soap.SOAPPublisher):
	"""UPnP requires OUT parameters to be returned in a slightly
	different way than the SOAPPublisher class does."""

	def _gotResult(self, result, request, methodName):
		response = SOAPpy.buildSOAP(kw=result, encoding=self.encoding)
		self._sendResponse(request, response)

	def _gotError(self, failure, request, methodName):
		e = failure.value
		status = 500
		if isinstance(e, SOAPpy.faultType):
			fault = e
		else:
			if isinstance(e, errorCode):
				status = e.status
			else:
				failure.printTraceback(file = log.logfile)
			fault = SOAPpy.faultType("%s:Server" % SOAPpy.NS.ENV_T, "Method %s failed." % methodName)
		response = SOAPpy.buildSOAP(fault, encoding=self.encoding)
		self._sendResponse(request, response, status=status)
