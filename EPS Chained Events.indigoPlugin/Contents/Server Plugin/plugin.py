#! /usr/bin/env python
# -*- coding: utf-8 -*-

# Core libraries
import indigo
import os
import sys
import time
import datetime
import json

# EPS 3.0 Libraries
import logging
from lib.eps import eps
from lib import ext
from lib import dtutil
from lib import iutil

# Plugin libraries
from random import randint # to randomize patrols

eps = eps(None)

################################################################################
# plugin - 	Basically serves as a shell for the main plugin functions, it passes
# 			all Indigo commands to the core engine to do the "standard" operations
#			and raises onBefore_ and onAfter_ if it wants to do something 
#			interesting with it.  The meat of the plugin is in here while the
#			EPS library handles the day-to-day and common operations.
################################################################################
class Plugin(indigo.PluginBase):

	# Define the plugin-specific things our engine needs to know
	TVERSION	= "3.3.0"
	PLUGIN_LIBS = ["cache", "plugcache", "actionsv2", "devices"] #["conditions", "cache", "actions"] #["cache"]
	UPDATE_URL 	= ""
		
	#
	# Init
	#
	def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
		indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)
		
		eps.__init__ (self)
		eps.loadLibs (self.PLUGIN_LIBS)
		
		#indigo.server.log (unicode(eps.plugcache.pluginCache))
		
		#self.core = core(self, libs=self.PLUGIN_LIBS, url=self.UPDATE_URL)
		#eps.plug.subscribeChanges (["devices", "variables"])
		#eps.plug.subscribeProtocols ({"zwave":"incoming|outgoing","insteon":"incoming|outgoing"})
		
		# TESTING
		#pc = plugcache(self)
		#retList = pc.getStateUIList (None)
		
		
		
	################################################################################
	# PLUGIN HANDLERS
	#
	# Raised onBefore_ and onAfter_ for interesting Indigo or custom commands that 
	# we want to intercept and do something with
	################################################################################	
	
	################################################################################	
	# PLUGIN
	################################################################################	
	
	# 
	# Change action terms
	#
	def onAfter_startup (self): 
		try:
			X = 1
			
		except Exception as e:
			self.logger.error (ext.getException(e))		
	
	
	################################################################################	
	# DEVICE CREATE/UPDATE EVENTS
	################################################################################
		
	def onAfter_validateDeviceConfigUi(self, valuesDict, typeId, devId):	
		try:
			if typeId == "Patrol":
				# Make sure the list actions are reset to edit and that if the stop action is blank it gets set now
				valuesDict["presetListActions"] = "edit"
				if valuesDict["whenTurnedOff"] == "": valuesDict["whenTurnedOff"] = "stay"
		
		except Exception as e:
			self.logger.error (ext.getException(e))		

		return (True, valuesDict, indigo.Dict())	
	
			
	################################################################################	
	# DEVICE RAISED EVENTS
	################################################################################		
	
	#
	# A form field changed, update defaults
	#
	def onAfter_formFieldChanged (self, valuesDict, typeId, devId):
		try:
			if typeId == "goToPreset": # Go to Preset Action
				if valuesDict["patrolDevice"] != "":
					valuesDict["presetsVisible"] = True
					
				# You cannot return to the off position AND resume
				if valuesDict["resumeAfterOverride"]:
					valuesDict["issueOffCommand"] = False
					
			elif typeId == "Patrol": # Patrol Device
				if valuesDict["actionDevice"] != "":
					valuesDict["deviceSelected"] = True
				else:
					valuesDict["deviceSelected"] = False
					
				if valuesDict["whenTurnedOff"] == "":
					valuesDict["whenTurnedOff"] = "stay"
								
		except Exception as e:
			self.logger.error (ext.getException(e))		
			
		return valuesDict	
	
	#			
	# Validate the action configuration (Indigo)
	#
	def onAfter_validateActionConfigUi(self, valuesDict, typeId, deviceId):	
		try:
			errorDict = indigo.Dict()
			
			if typeId == "goToPreset": # Go to Preset Action
				if valuesDict["duration"] == "" or valuesDict["duration"] == "0":
					errorDict["duration"] = "Duration cannot be nothing"
					errorDict["showAlertText"] = "Invalid duration."
					return (False, valuesDict, errorDict)		 
				
		except Exception as e:
			self.logger.error (ext.getException(e))
			
		return (True, valuesDict, errorDict)
			
	
	#
	# Our device was turned off
	#
	def onDeviceCommandTurnOff (self, dev):	
		try:
			if dev.deviceTypeId == "Patrol":
				# Preset 3001 means to stay no matter what
				if dev.states["nextPreset"] == 3001 or dev.pluginProps["whenTurnedOff"] == "stay": 
					states = iutil.updateState ("nextPreset", 0)
					states = iutil.updateState ("currentPreset", 0, states)
					dev.updateStatesOnServer (states)
					
					return True
				else:
					presetData = dev.pluginProps["presetItems"]			
					presetItems = json.loads(presetData)
					
					for x in range(0, len(presetItems)):
						if x == int(dev.pluginProps["whenTurnedOff"]):
							ret = eps.actv2.runAction (dev, presetItems[x]["key"], "Preset {0}".format(str(x)))
							
							states = iutil.updateState ("nextPreset", 0)
							states = iutil.updateState ("currentPreset", 0, states)
							states = iutil.updateState ("overrideActive", False, states)
							states = iutil.updateState ("overrideResumePatrol", 0, states)
							dev.updateStatesOnServer (states)
							
							return True
				
				
		except Exception as e:
			self.logger.error (ext.getException(e))		
			
		return False
		
	#
	# Our device was turned on
	#
	def onDeviceCommandTurnOn (self, dev):	
		try:
			if dev.deviceTypeId == "Patrol":
				# We are only running the first action (or continuing) here, the rest run on concurrent threads
				return self.runPatrolAction (dev, 0)
				
		except Exception as e:
			self.logger.error (ext.getException(e))		
			
		return False
		
	#
	# Our device brightness was changed
	#
	def onDeviceCommandSetBrightness (self, dev, value):	
		try:
			if dev.deviceTypeId == "Patrol":
				presetItems = json.loads(dev.pluginProps["presetItems"])
				
				if value > len(presetItems): value = len(presetItems)
				
				presetItem = presetItems[value - 1]
				
				d = indigo.server.getTime()
				d = dtutil.dateAdd (dev.pluginProps["dimDurationType"], int(dev.pluginProps["dimWhenPatrolling"]), d)
				
				# Change our normal run time state since no matter what we are running for this time as if it were a normal patrol
				d = dtutil.dateDiff ("seconds", datetime.datetime.strptime (dev.states["nextPresetTime"], "%Y-%m-%d %H:%M:%S"), indigo.server.getTime())				
				if d <= 0: 
					# There isn't a patrol running, use the current date and time						
					d = indigo.server.getTime()
				else:
					# There is a patrol running, use the current patrol date and time
					d = datetime.datetime.strptime (dev.states["nextPresetTime"], "%Y-%m-%d %H:%M:%S")
				
				d = dtutil.dateAdd (dev.pluginProps["dimDurationType"], int(dev.pluginProps["dimWhenPatrolling"]), d)

				# Set the time to go to this manual preset
				states = iutil.updateState ("overrideUntil", d.strftime("%Y-%m-%d %H:%M:%S"))
				states = iutil.updateState ("overrideActive", True, states)
				states = iutil.updateState ("nextPresetTime", d.strftime("%Y-%m-%d %H:%M:%S"), states)
				
				states = iutil.updateState ("onOffState", True,states)
				states = iutil.updateState ("brightnessLevel", value, states)
				states = iutil.updateState ("currentPreset", value, states)
				
				if dev.states["onOffState"] == False and dev.pluginProps["dimWhenPatrolling"] != "0" and dev.pluginProps["dimWhenPatrolling"] != "":
					# It's not patrolling, run the off command after this
					states = iutil.updateState ("currentPreset", 2000, states) # Forces it to stop because 1000 is way above anything we could actually have there
					states = iutil.updateState ("nextPreset", 2001, states)

				elif dev.pluginProps["dimWhenPatrolling"] == "0" or dev.pluginProps["dimWhenPatrolling"] == "":
					# Move the camera into position and stop there
					states = iutil.updateState ("currentPreset", 3000, states) # Forces it to stop because 1000 is way above anything we could actually have there
					states = iutil.updateState ("nextPreset", 3001, states)
				
				dev.updateStatesOnServer (states)
				
				ret = eps.actv2.runAction (dev, presetItem["key"], "'{0}' brightness changed, executing preset {1}".format(dev.name, str(value)))

				return True
		
		except Exception as e:
			self.logger.error (ext.getException(e))		
			
		return False
		
	################################################################################	
	# PLUGIN RAISED EVENTS
	################################################################################			
	
	#
	# Concurrent thread
	#
	def onAfter_runConcurrentThread (self):
		try:
			for dev in indigo.devices.iter(self.pluginId + ".Patrol"):
				try:
					if dev.states["onOffState"] and dev.states["nextPresetTime"]:
						d = dtutil.dateDiff ("seconds", datetime.datetime.strptime (dev.states["nextPresetTime"], "%Y-%m-%d %H:%M:%S"), indigo.server.getTime())				
						if d <= 0: 
							self.logger.threaddebug ("Running patrol action because the current patrol expired " + dev.states["nextPresetTime"])
							self.runPatrolAction (dev, dev.states["nextPreset"])
				
				except:
					continue # The device isn't in the database, failsafe to prevent race errors
								
		except Exception as e:
			self.logger.error (ext.getException(e))		


		
	################################################################################	
	# PATROL FORM EVENTS
	################################################################################
			
	#
	# Update patrol point
	#
	def onAfter_actionUpdateListButton (self, valuesDict, typeId, devId):		
		try:
			presetItems = json.loads(valuesDict["presetItems"])
			for presetItem in presetItems:
				if presetItem["key"] == valuesDict["actionItemLibKey"]:
					presetData = presetItem	
			
			actionItems = json.loads(valuesDict["actionItemLibData"])
			for actionData in actionItems:
				if actionData["key"] == valuesDict["actionItemLibKey"]:
					actionItem = actionData	
					
			if valuesDict["duration"] == "": valuesDict["duration"] = "0"
			if valuesDict["randomize"] == "": valuesDict["randomize"] = "0"
			presetData["duration"] = valuesDict["duration"]
			presetData["durationInterval"] = valuesDict["durationInterval"]
			presetData["randomize"] = valuesDict["randomize"]
			presetData["oncomplete"] = valuesDict["onComplete"]
			#presetData["name"] = str(presetData["order"]) + ": " + actionItem["objectName"] + " (" + presetData["duration"] + " seconds)"
			presetData = self.generatePresetName (presetData, actionItem, valuesDict)
			
			# Now recreate the JSON data
			newPresetList = []
			
			for presetItemEx in presetItems:
				if presetItemEx["key"] != valuesDict["actionItemLibKey"]:
					newPresetList.append(presetItemEx)
				else:
					newPresetList.append(presetData)
	
			jdata = json.dumps(newPresetList)
			valuesDict["presetItems"] = jdata
			
			# Reset the fields to nothing
			valuesDict["actionType"] = "device"
			valuesDict["actionDevice"] = ""
			valuesDict["duration"] = "10"
			valuesDict["onComplete"] = "next"
			valuesDict["name"] = ""
			valuesDict["durationInterval"] = "seconds"
			valuesDict["deviceSelected"] = False
			valuesDict["randomize"] = "0"
			
			# Turn off the update button, turn on add and re-enable the list for actions
			valuesDict["presetsUnlocked"] = True
			valuesDict["addVisible"] = True
			valuesDict["updateVisible"] = False
			
		except Exception as e:
			self.logger.error (ext.getException(e))		
			
		return valuesDict	
		
	#
	# Add patrol point
	#
	def onAfter_actionAddToListButton (self, valuesDict, typeId, devId):	
		try:
			if 'presetItems' not in valuesDict:
				valuesDict['presetItems'] = json.dumps([])  # Empty list in JSON container	
			
			presetList = valuesDict["presetItems"]
			presetItems = json.loads(presetList)
						
			# We get our data after actionsv2 has saved its data and cleared the fields, we'll have to read in
			# the actions data using the special key field that should now be in our valuesDict
			actionItems = json.loads(valuesDict["actionItemLibData"])
			for actionData in actionItems:
				if actionData["key"] == valuesDict["actionItemLibKey"]:
					actionItem = actionData								
			
			presetData = {}
			
			presetData["key"] = actionItem["key"]
			
			if valuesDict["duration"] == "": valuesDict["duration"] = "0"
			if valuesDict["randomize"] == "": valuesDict["randomize"] = "0"
			presetData["duration"] = valuesDict["duration"]
			presetData["durationInterval"] = valuesDict["durationInterval"]
			presetData["randomize"] = valuesDict["randomize"]
			presetData["oncomplete"] = valuesDict["onComplete"]
			
			presetData["order"] = len(presetItems) + 1
			#presetData["name"] = str(presetData["order"]) + ": " + actionItem["objectName"] + " (" + presetData["duration"] + " seconds)"
			presetData = self.generatePresetName (presetData, actionItem, valuesDict)
			
			presetItems.append (presetData)
			
			jdata = json.dumps(presetItems)
			valuesDict["presetItems"] = jdata
			
			# Reset the fields to nothing
			valuesDict["actionType"] = "device"
			valuesDict["actionDevice"] = ""
			valuesDict["duration"] = "10"
			valuesDict["onComplete"] = "next"
			valuesDict["name"] = ""
			valuesDict["durationInterval"] = "seconds"
			valuesDict["deviceSelected"] = False
			valuesDict["randomize"] = "0"
			
			#indigo.server.log(unicode(presetData))
			#indigo.server.log(unicode(valuesDict))
			
						
		except Exception as e:
			self.logger.error (ext.getException(e))	
			
		return valuesDict	

	#
	# Read JSON data for patrol points
	#

	def actionListPresetsForDevice (self, args, valuesDict):	
		retList = list()
		
		try:
			if 'patrolDevice' not in valuesDict:
				return retList
				
			dev = indigo.devices[int(valuesDict["patrolDevice"])]
			
			if 'presetItems' not in dev.pluginProps:
				return retList
			
			presetItems = json.loads(dev.pluginProps["presetItems"])
			for presetItem in presetItems:
				option = (presetItem["key"], presetItem["name"])
				retList.append(option)		
		
		except Exception as e:
			self.logger.error (ext.getException(e))	
		
		return retList
		
	#
	# Read JSON data for patrol points
	#
	def listPatrolPoints (self, args, valuesDict):	
		retList = list()
		
		try:
			if 'presetItems' not in valuesDict:
				return retList
				
			presetItems = valuesDict["presetItems"]			
			jdata = json.loads(presetItems)
			
			for item in jdata:
				option = (item["key"], item["name"])
				retList.append(option)		
		
		except Exception as e:
			self.logger.error (ext.getException(e))	
		
		return retList
	
	#
	# Read JSON data for patrol points to populate the onOffCommandReceived list
	#	
	def listOffCommandOptions (self, args, valuesDict):	
		retList = list()
				
		try:
			option = ("stay", "Stop patrol and stay on current preset")
			retList.append(option)	
		
			if 'presetItems' not in valuesDict:
				return retList
				
			presetItems = valuesDict["presetItems"]			
			jdata = json.loads(presetItems)
			
			for x in range(0, len(jdata)):
				option = (str(x), "Go to preset " + jdata[x]["name"])
				retList.append(option)	
					
		except Exception as e:
			self.logger.error (ext.getException(e))	
		
		return retList
		
	
		
	#
	# The patrol list execute button is clicked
	#
	def btnPatrolListAction (self, valuesDict, typeId, devId):
		try:
			if len(valuesDict["presets"]) == 0:
				errorsDict = indigo.Dict()
				errorsDict["presetListActions"] = "You must select a preset on the list to take an action"
				errorsDict["showAlertText"] = "No preset was selected from the list to act on."
				return valuesDict, errorsDict
				
			if len(valuesDict["presets"]) > 1:
				errorsDict = indigo.Dict()
				errorsDict["presetListActions"] = "Too many presets were selected, please select just one"
				errorsDict["showAlertText"] = "You can only perform an action on one preset at a time."
				return valuesDict, errorsDict
		
			# First determine what we are on and load up the settings for it
			for preset in valuesDict["presets"]:
				# We only really care about the last item, multiples are not supported
				valuesDict["actionItemLibKey"] = preset
				
			# Now pull the plugin data for this preset
			itemKey = valuesDict["presets"][0] # Since we only allow one selection, it's easy to get the key
			
			presetItem = ext.getJSONDictForKey (valuesDict["presetItems"], itemKey)
			actionItem = ext.getJSONDictForKey (valuesDict["actionItemLibData"], itemKey)
			
			if valuesDict["presetListActions"] == "edit":
				valuesDict["presetsUnlocked"] = False
				
				# We add order and seconds to the name automatically, we need to strip those out
				valuesDict["name"] = self.stripPresetName (presetItem)				
				valuesDict["onComplete"] = presetItem["oncomplete"]
				valuesDict["duration"] = presetItem["duration"]
				valuesDict["durationInterval"] = presetItem["durationInterval"]
				valuesDict["randomize"] = presetItem["randomize"]
				valuesDict["addVisible"] = False
				valuesDict["updateVisible"] = True
				valuesDict["deviceSelected"] = True
				
				valuesDict = eps.actv2.loadFieldValuesFromDict (valuesDict, actionItem)
			
			elif valuesDict["presetListActions"] == "remove":
				key = presetItem["key"]
				valuesDict = eps.actv2.deleteActionItem (valuesDict, key)
				
				presetItems = json.loads(valuesDict["presetItems"])
				newPresetItems = []
				
				# Get this item
				for item in presetItems:
					if item["key"] == key:
						presetOrder = item["order"]
				
				# Rebuild without this item
				for item in presetItems:
					if item["key"] != key:
						if item["order"] > presetOrder:
							valuesDict["name"] = self.stripPresetName (item)
							item["order"] = item["order"] - 1
							actionItem = ext.getJSONDictForKey (valuesDict["actionItemLibData"], item["key"])
							item = self.generatePresetName (item, actionItem, valuesDict)
							valuesDict["name"] = ""
							
						newPresetItems.append (item)
			
				jdata = json.dumps(newPresetItems)
				valuesDict["presetItems"] = jdata
				
			elif valuesDict["presetListActions"] == "dupe":
				valuesDict = eps.actv2.duplicateActionItem (valuesDict, presetItem["key"])
				
				newKey = valuesDict["actionItemLibKey"] # ActionsV2 updated this in the dupe function
				valuesDict["actionItemLibKey"] = "" # Safety precaution since it's staying populated and so much looks to it
				
				newPresetItem = dict(presetItem)	
				newPresetItem["key"] = newKey
				
				#indigo.server.log(presetItem["key"])
				#indigo.server.log(newKey)
												
				#indigo.server.log(unicode(newPresetItem))
				
				presetItems = json.loads(valuesDict["presetItems"])
				valuesDict["name"] = "Copy of " + self.stripPresetName (presetItem)	
				newPresetItem["order"] = len(presetItems) + 1
				newPresetItem = self.generatePresetName (newPresetItem, actionItem, valuesDict)
				valuesDict["name"] = ""
								
				presetItems.append(newPresetItem)
				jdata = json.dumps(presetItems)
				valuesDict["presetItems"] = jdata
				
			elif valuesDict["presetListActions"] == "up":
				presetData = valuesDict["presetItems"]			
				presetItems = json.loads(presetData)
				
				# Get the key above this one
				prevItem = ""
				for item in presetItems:
					if item["key"] != presetItem["key"]:
						prevItem = item
					else:
						break # don't process further once we find this key
						
				if len(prevItem) == 0: 
					errorsDict = indigo.Dict()
					errorsDict["showAlertText"] = "The select item is the first item and cannot move up further."
					return valuesDict, errorsDict
						
				# Now reassemble
				newPresetItems = []
				for item in presetItems:
					if item["key"] == prevItem["key"]:
						valuesDict["name"] = self.stripPresetName (presetItem)
						presetItem["order"] = presetItem["order"] - 1
						actionItem = ext.getJSONDictForKey (valuesDict["actionItemLibData"], presetItem["key"])
						presetItem = self.generatePresetName (presetItem, actionItem, valuesDict)
						valuesDict["name"] = ""
						newPresetItems.append (presetItem)
					elif item["key"] == presetItem["key"]:
						valuesDict["name"] = self.stripPresetName (prevItem)
						actionItem = ext.getJSONDictForKey (valuesDict["actionItemLibData"], prevItem["key"])
						prevItem["order"] = prevItem["order"] + 1
						prevItem = self.generatePresetName (prevItem, actionItem, valuesDict)
						valuesDict["name"] = ""
						newPresetItems.append (prevItem)
					else:
						newPresetItems.append (item)
						
				jdata = json.dumps(newPresetItems)
				valuesDict["presetItems"] = jdata
				
			elif valuesDict["presetListActions"] == "down":
				presetData = valuesDict["presetItems"]			
				presetItems = json.loads(presetData)
				
				# Get the key below this one
				nextItem = ""
				getNext = 0
				for item in presetItems:
					if getNext == 1:
						nextItem = item
						break # all done
				
					if item["key"] == presetItem["key"]:
						getNext = 1
						
				if len(nextItem) == 0: 
					errorsDict = indigo.Dict()
					errorsDict["showAlertText"] = "The select item is the last item and cannot move down further."
					return valuesDict, errorsDict
					
				# Now reassemble
				newPresetItems = []
				for item in presetItems:
					if item["key"] == presetItem["key"]:
						valuesDict["name"] = self.stripPresetName (nextItem)
						nextItem["order"] = nextItem["order"] - 1
						actionItem = ext.getJSONDictForKey (valuesDict["actionItemLibData"], nextItem["key"])
						nextItem = self.generatePresetName (nextItem, actionItem, valuesDict)
						valuesDict["name"] = ""
						newPresetItems.append (nextItem)
					elif item["key"] == nextItem["key"]:
						valuesDict["name"] = self.stripPresetName (presetItem)	
						presetItem["order"] = presetItem["order"] + 1
						actionItem = ext.getJSONDictForKey (valuesDict["actionItemLibData"], presetItem["key"])
						presetItem = self.generatePresetName (presetItem, actionItem, valuesDict)
						valuesDict["name"] = ""
						newPresetItems.append (presetItem)
					else:
						newPresetItems.append (item)
						
				jdata = json.dumps(newPresetItems)
				valuesDict["presetItems"] = jdata
						
		except Exception as e:
			self.logger.error (ext.getException(e))		
			
		return valuesDict	
		
	################################################################################	
	# MISC FUNCTIONS
	################################################################################
		
	#
	# Strip the preset number from the beginning and the duration from the end of a preset name
	#
	def stripPresetName (self, presetItem):
		try:
			presetName = presetItem["name"]
			presetName = presetName.replace (str(presetItem["order"]) + ": ", "", 1)
			presetName = presetName.replace (" (" + presetItem["duration"] + " " + presetItem["durationInterval"] + ")", "", 1)
			
		except Exception as e:
			self.logger.error (ext.getException(e))		
			
		return presetName	

			
	#
	# Generate preset name based on preset settings (done here so if we change it in the future it only has to be changed in one place)
	#
	def generatePresetName (self, presetData, actionItem, valuesDict):
		try:
			if valuesDict["name"] == "":
				presetData["name"] = "{0}: {1} ({2} {3})".format(str(presetData["order"]), actionItem["objectName"], presetData["duration"], presetData["durationInterval"])
				#presetData["name"] = str(presetData["order"]) + ": " + actionItem["objectName"] + " (" + presetData["duration"] + " seconds)"
			else:
				presetData["name"] = "{0}: {1} ({2} {3})".format(str(presetData["order"]), valuesDict["name"], presetData["duration"], presetData["durationInterval"])
				#presetData["name"] = str(presetData["order"]) + ": " + valuesDict["name"] + " (" + presetData["duration"] + " seconds)"
		
		except Exception as e:
			self.logger.error (ext.getException(e))		
			
		return presetData		

	################################################################################	
	# ACTIONS
	################################################################################
	
	#
	# Go to preset	
	#
	def actionsGoToPreset (self, action):
		try:
			dev = indigo.devices[int(action.props["patrolDevice"])]	
			
			d = indigo.server.getTime()
			d = dtutil.dateAdd (action.props["durationInterval"], int(action.props["duration"]), d)
			
			# Set the time to go to this manual preset
			states = iutil.updateState ("overrideUntil", d.strftime("%Y-%m-%d %H:%M:%S"))
			states = iutil.updateState ("overrideActive", True, states)
			
			# Change our normal run time state since no matter what we are running for this time as if it were a normal patrol
			d = dtutil.dateDiff ("seconds", datetime.datetime.strptime (dev.states["nextPresetTime"], "%Y-%m-%d %H:%M:%S"), indigo.server.getTime())				
			if d <= 0: 
				# There isn't a patrol running, use the current date and time						
				d = indigo.server.getTime()
			else:
				# There is a patrol running, use the current patrol date and time
				d = datetime.datetime.strptime (dev.states["nextPresetTime"], "%Y-%m-%d %H:%M:%S")
				
			d = dtutil.dateAdd (action.props["durationInterval"], int(action.props["duration"]), d)

			states = iutil.updateState ("nextPresetTime", d.strftime("%Y-%m-%d %H:%M:%S"), states)
			
			if action.props["resumeAfterOverride"] == False and dev.states["onOffState"] == False:
				# Set the current and next presets to be high enough to trigger the device to turn itself off after this current run
				states = iutil.updateState ("currentPreset", 1000, states) # Forces it to stop because 1000 is way above anything we could actually have there
				states = iutil.updateState ("nextPreset", 1001, states)
				
			if action.props["resumeAfterOverride"] == False and action.props["issueOffCommand"]:
				# Setting current to 2000 will force it to run Off instead of continuing
				states = iutil.updateState ("currentPreset", 2000, states)
				states = iutil.updateState ("nextPreset", 2001, states)
			
			#states = iutil.updateState ("nextPresetTime", d.strftime("%Y-%m-%d %H:%M:%S"))
			states = iutil.updateState ("paused", False, states)
			states = iutil.updateState ("onOffState", True, states) # Failsafe, it seems to go off after two rounds (after reload it works fine, then it runs two presets and turns itself off: dev onOffState reading off and we are re-saving it?) - need to investigate this
			
			dev.updateStatesOnServer (states)
			
			dev = indigo.devices[int(action.props["patrolDevice"])]	 # Force a refresh
			
			ret = eps.actv2.runAction (dev, action.props["presets"], "Action raised to go to a preset on '{0}'".format(dev.name))
				
		except Exception as e:
			self.logger.error (ext.getException(e))		

		
	################################################################################	
	# PATROL EVENTS
	################################################################################
	
	#
	# Run the patrol action using the zero based index
	#
	def runPatrolAction (self, dev, i):
		try:
			self.logger.debug ("Running patrol action for preset {0}".format(str(i)))
			
			presetData = dev.pluginProps["presetItems"]			
			presetItems = json.loads(presetData)
			d = indigo.server.getTime()
			
			if i < 1000: # Since we use 1000 in actions to force it to stop and 2000 to force it to turn off			
				for x in range(0, len(presetItems)):
					if x == i:
						randnumber = 0
					
						if int(presetItems[x]["randomize"]) != 0:
							randnumber = randint(int(presetItems[x]["randomize"]) * -1, int(presetItems[x]["randomize"]))
						
						runtime = int(presetItems[x]["duration"]) + randnumber
						
						self.logger.debug ("Running patrol preset {0} on {1} for {2} {3}".format(presetItems[x]["name"], dev.name, str(runtime), presetItems[x]["durationInterval"]))		
					
						d = dtutil.dateAdd (presetItems[x]["durationInterval"], runtime, d)
						states = iutil.updateState ("nextPresetTime", d.strftime("%Y-%m-%d %H:%M:%S"))
						states = iutil.updateState ("paused", False, states)
						states = iutil.updateState ("onOffState", True, states) # Failsafe, it seems to go off after two rounds (after reload it works fine, then it runs two presets and turns itself off: dev onOffState reading off and we are re-saving it?) - need to investigate this
						states = iutil.updateState ("brightnessLevel", i + 1, states)
						states = iutil.updateState ("currentPreset", x, states)
						states = iutil.updateState ("nextPreset", x + 1, states)
					
						dev.updateStatesOnServer (states)
					
						ret = eps.actv2.runAction (dev, presetItems[x]["key"], "Preset {0}".format(str(x)))

						return ret
						
				# If we get here then we are likely outside of our patrol presets, check if we are running continuously or stopping now
				if dev.pluginProps["runManually"] == False:
					randnumber = 0
				
					if int(dev.pluginProps["randomizePark"]) != 0:
						randnumber = randint(int(dev.pluginProps["randomizePark"]) * -1, int(dev.pluginProps["randomizePark"]))
					
					runtime = int(dev.pluginProps["park"]) + randnumber	
					
					self.logger.info ("Patrol device '{0}' waiting {1} {2} until next round robin".format(dev.name, str(runtime), dev.pluginProps["parkDurationType"]))				
					
					d = indigo.server.getTime()
					d = dtutil.dateAdd (dev.pluginProps["parkDurationType"], runtime, d)
					
					states = iutil.updateState ("nextPresetTime", d.strftime("%Y-%m-%d %H:%M:%S"))
					states = iutil.updateState ("currentPreset", 0, states)
					states = iutil.updateState ("nextPreset", 0, states)
					states = iutil.updateState ("onOffState", True, states)
					states = iutil.updateState ("brightnessLevel", 99, states)
					
					dev.updateStatesOnServer (states)
					
					return True
					
			# If we got here then the loop didn't run, likely because we ran out of loops to run and we are not running continuously
			self.logger.threaddebug ("{0} is outside of the {1} presets available, {2} is now shutting off".format(str(i), str(len(presetItems)), dev.name))
			states = iutil.updateState ("nextPreset", 0)
			states = iutil.updateState ("currentPreset", 0, states)
			states = iutil.updateState ("onOffState", False, states) # So the concurrent never runs since this is now off
			states = iutil.updateState ("brightnessLevel", 0, states)
			
			dev.updateStatesOnServer (states)
			
			if i == 2001:
				# That means to turn it off so we honor the "off" setting in the device
				self.onDeviceCommandTurnOff (dev)
				
		except Exception as e:
			self.logger.error (ext.getException(e))		
			
		return False	
		

			
	################################################################################
	# DEVELOPMENT TESTING SANDBOX, FUNCTIONS IN THIS AREA GET MOVED ELSEWHERE LATER
	################################################################################

	# Development testing
	def devTest (self):
		try:
			indigo.server.log ("These are not the droids you are looking for.  Move along.  Move along.")
					
		except Exception as e:
			self.logger.error (ext.getException(e))			

	
	################################################################################
	# INDIGO COMMAND HAND-OFFS
	#
	# Everything below here are standard Indigo plugin actions that get handed off
	# to the engine, they really shouldn't change from plugin to plugin
	################################################################################
	
	################################################################################
	# INDIGO PLUGIN EVENTS
	################################################################################		
	
	# System
	def startup(self): return eps.plug.startup()
	def shutdown(self): return eps.plug.shutdown()
	def runConcurrentThread(self): return eps.plug.runConcurrentThread()
	def stopConcurrentThread(self): return eps.plug.stopConcurrentThread()
	def __del__(self): return eps.plug.delete()
	
	# UI
	def validatePrefsConfigUi(self, valuesDict): return eps.plug.validatePrefsConfigUi(valuesDict)
	def closedPrefsConfigUi(self, valuesDict, userCancelled): return eps.plug.closedPrefsConfigUi(valuesDict, userCancelled)
	
	################################################################################
	# INDIGO DEVICE EVENTS
	################################################################################
	
	# Basic comm events
	def deviceStartComm (self, dev): return eps.plug.deviceStartComm (dev)
	def deviceUpdated (self, origDev, newDev): return eps.plug.deviceUpdated (origDev, newDev)
	def deviceStopComm (self, dev): return eps.plug.deviceStopComm (dev)
	def deviceDeleted(self, dev): return eps.plug.deviceDeleted(dev)
	def actionControlDimmerRelay(self, action, dev): return eps.plug.actionControlDimmerRelay(action, dev)
	
	# UI Events
	def getDeviceDisplayStateId(self, dev): return eps.plug.getDeviceDisplayStateId (dev)
	def validateDeviceConfigUi(self, valuesDict, typeId, devId): return eps.plug.validateDeviceConfigUi(valuesDict, typeId, devId)
	def closedDeviceConfigUi(self, valuesDict, userCancelled, typeId, devId): return eps.plug.closedDeviceConfigUi(valuesDict, userCancelled, typeId, devId)		
	
	################################################################################
	# INDIGO PROTOCOL EVENTS
	################################################################################
	def zwaveCommandReceived(self, cmd): return eps.plug.zwaveCommandReceived(cmd)
	def zwaveCommandSent(self, cmd): return eps.plug.zwaveCommandSent(cmd)
	def insteonCommandReceived (self, cmd): return eps.plug.insteonCommandReceived(cmd)
	def insteonCommandSent (self, cmd): return eps.plug.insteonCommandSent(cmd)
	def X10CommandReceived (self, cmd): return eps.plug.X10CommandReceived(cmd)
	def X10CommandSent (self, cmd): return eps.plug.X10CommandSent(cmd)

	################################################################################
	# INDIGO VARIABLE EVENTS
	################################################################################
	
	# Basic comm events
	def variableCreated(self, var): return eps.plug.variableCreated(var)
	def variableUpdated (self, origVar, newVar): return eps.plug.variableUpdated (origVar, newVar)
	def variableDeleted(self, var): return self.variableDeleted(var)
		
	################################################################################
	# INDIGO EVENT EVENTS
	################################################################################
	
	# Basic comm events
	
	# UI
	def validateEventConfigUi(self, valuesDict, typeId, eventId): return eps.plug.validateEventConfigUi(valuesDict, typeId, eventId)
	def closedEventConfigUi(self, valuesDict, userCancelled, typeId, eventId): return eps.plug.closedEventConfigUi(valuesDict, userCancelled, typeId, eventId)
		
	################################################################################
	# INDIGO ACTION EVENTS
	################################################################################
	
	# Basic comm events
	def actionGroupCreated(self, actionGroup): eps.plug.actionGroupCreated(actionGroup)
	def actionGroupUpdated (self, origActionGroup, newActionGroup): eps.plug.actionGroupUpdated (origActionGroup, newActionGroup)
	def actionGroupDeleted(self, actionGroup): eps.plug.actionGroupDeleted(actionGroup)
		
	# UI
	def validateActionConfigUi(self, valuesDict, typeId, actionId): return eps.plug.validateActionConfigUi(valuesDict, typeId, actionId)
	def closedActionConfigUi(self, valuesDict, userCancelled, typeId, actionId): return eps.plug.closedActionConfigUi(valuesDict, userCancelled, typeId, actionId)
		
	################################################################################
	# INDIGO TRIGGER EVENTS
	################################################################################
	
	# Basic comm events
	def triggerStartProcessing(self, trigger): return eps.plug.triggerStartProcessing(trigger)
	def triggerStopProcessing(self, trigger): return eps.plug.triggerStopProcessing(trigger)
	def didTriggerProcessingPropertyChange(self, origTrigger, newTrigger): return eps.plug.didTriggerProcessingPropertyChange(origTrigger, newTrigger)
	def triggerCreated(self, trigger): return eps.plug.triggerCreated(trigger)
	def triggerUpdated(self, origTrigger, newTrigger): return eps.plug.triggerUpdated(origTrigger, newTrigger)
	def triggerDeleted(self, trigger): return eps.plug.triggerDeleted(trigger)
                                   
	# UI
	
	################################################################################
	# INDIGO SYSTEM EVENTS
	################################################################################
	
	# Basic comm events
	
	# UI
	
	################################################################################
	# EPS EVENTS
	################################################################################		
	
	# Plugin menu actions
	def pluginMenuSupportData (self): return eps.plug.pluginMenuSupportData ()
	def pluginMenuSupportDataEx (self): return eps.plug.pluginMenuSupportDataEx ()
	def pluginMenuSupportInfo (self): return eps.plug.pluginMenuSupportInfo ()
	def pluginMenuCheckUpdates (self): return eps.plug.pluginMenuCheckUpdates ()
	
	# UI Events
	def getCustomList (self, filter="", valuesDict=None, typeId="", targetId=0): return eps.ui.getCustomList (filter, valuesDict, typeId, targetId)
	def formFieldChanged (self, valuesDict, typeId, devId): return eps.plug.formFieldChanged (valuesDict, typeId, devId)
	
	# Actions Events
	def actionAddToListButton (self, valuesDict, typeId, devId): return eps.plug.actionAddToListButton (valuesDict, typeId, devId)
	def actionUpdateListButton (self, valuesDict, typeId, devId): return eps.plug.actionUpdateListButton (valuesDict, typeId, devId)
	
	
	################################################################################
	# ADVANCED PLUGIN ACTIONS (v3.3.0)
	################################################################################

	# Plugin menu advanced plugin actions 
	def advPluginDeviceSelected (self, valuesDict, typeId): return eps.plug.advPluginDeviceSelected (valuesDict, typeId)
	def btnAdvDeviceAction (self, valuesDict, typeId): return eps.plug.btnAdvDeviceAction (valuesDict, typeId)
	def btnAdvPluginAction (self, valuesDict, typeId): return eps.plug.btnAdvPluginAction (valuesDict, typeId)
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	