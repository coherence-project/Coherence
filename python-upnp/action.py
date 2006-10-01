# Elisa - Home multimedia server
# Copyright (C) 2006 Fluendo, S.A. (www.fluendo.com).
# All rights reserved.
# 
# This software is available under three license agreements.
# 
# There are various plugins and extra modules for Elisa licensed
# under the MIT license. For instance our upnp module uses this license.
# 
# The core of Elisa is licensed under GPL version 2.
# See "LICENSE.GPL" in the root of this distribution including a special 
# exception to use Elisa with Fluendo's plugins.
# 
# The GPL part is also available under a commerical licensing
# agreement.
# 
# The second license is the Elisa Commercial License Agreement.
# This license agreement is available to licensees holding valid
# Elisa Commercial Agreement licenses.
# See "LICENSE.Elisa" in the root of this distribution.


class Argument:

    def __init__(self, name, direction, state_variable):
        self.name = name
        self.direction = direction
        self.state_variable = state_variable

    def get_name(self):
        return self.name

    def get_direction(self):
        return self.direction

    def get_state_variable(self):
        return self.state_variable
    
    def __repr__(self):
        return "Argument: %s, %s, %s" % (self.get_name(),
                                         self.get_direction(), self.get_state_variable())

class Action:

    def __init__(self, service, name, arguments_list):
        self.service = service
        self.name = name
        self.arguments_list = arguments_list

    def get_name(self):
        return self.name

    def get_arguments_list(self):
        return self.arguments_list

    def get_service(self):
        return self.service

    def launch(self):
        pass

    def __repr__(self):
        return "Action: %s (%s args)" % (self.get_name(),
                                         len(self.get_arguments_list()))
