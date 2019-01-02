import os
import unittest
import math
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
import logging
from functools import partial

#
# PointerBasedUSCalibration
#

class PointerBasedUSCalibration(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "Pointer-Based US Calibration" # TODO make this more human readable by adding spaces
    self.parent.categories = ["IGT"]
    self.parent.dependencies = []
    self.parent.contributors = ["Matthew S. Holden (PerkLab, Queen's University)"] # replace with "Firstname Lastname (Organization)"
    self.parent.helpText = """
    This module is intended for calibrating an ultrasound probe using the pointer-based method.
    """
    self.parent.acknowledgementText = """
    This file was originally developed by Matthew S. Holden, PerkLab, Queen's University and was supported by OCAIRO, NSERC, and CIHR.
    """ # replace with organization, grant and thanks.

#
# PointerBasedUSCalibrationWidget
#

class PointerBasedUSCalibrationWidget(ScriptedLoadableModuleWidget):
  """Uses ScriptedLoadableModuleWidget base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """
  
  RESULTS_IMAGE_POINTS_INDEX = 0
  RESULTS_PROBE_POINTS_INDEX = 1
  RESULTS_ERROR_INDEX = 2
  RESULTS_DELETE_INDEX = 3
  RESULTS_NUM_INDICES = 4 # Should always be one greater than the largest index
  
  IMAGE_PREFIX_GUESS = [ "Image_" ]
  STYLUSTIP_TO_PROBE_PREFIX_GUESS = [ "StylusTipTo", "NeedleTipTo" ]
  IMAGE_TO_PROBE_PREFIX_GUESS = [ "ImageToProbe" ]
  
  ULTRASOUND_IMAGE_ROLE = "UltrasoundImage"

  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)
    
    # Instantiate and connect widgets ...
    self.pbucLogic = PointerBasedUSCalibrationLogic() # Have reference to an instance of the logic
    
    #
    # Tracked ultrasound playback toolbox
    #
    self.playToolBox = qt.QToolBox()
    self.layout.addWidget( self.playToolBox )
    
    #
    # Real-time playback
    #
    self.realTimeFrame = qt.QFrame( self.playToolBox )
    self.realTimeLayout = qt.QVBoxLayout( self.realTimeFrame )
    
    self.connectorNodeSelector = slicer.qMRMLNodeComboBox()
    self.connectorNodeSelector.nodeTypes = [ "vtkMRMLIGTLConnectorNode" ]
    self.connectorNodeSelector.addEnabled = False
    self.connectorNodeSelector.removeEnabled = False
    self.connectorNodeSelector.noneEnabled = False
    self.connectorNodeSelector.showHidden = False
    self.connectorNodeSelector.showChildNodeTypes = False
    self.connectorNodeSelector.setMRMLScene( slicer.mrmlScene )
    self.connectorNodeSelector.setToolTip( "Select the connector node for playback." )
    self.realTimeLayout.addWidget( self.connectorNodeSelector )
    
    self.freezeButton = qt.QPushButton( "Freeze" )
    self.freezeButton.setToolTip( "Freeze the connection." )
    self.realTimeLayout.addWidget( self.freezeButton )
    
    #
    # Recorded sequence playback
    #
    self.sequenceFrame = qt.QFrame( self.playToolBox )
    self.sequenceLayout = qt.QVBoxLayout( self.sequenceFrame )
    
    self.sequenceBrowserNodeSelector = slicer.qMRMLNodeComboBox()
    self.sequenceBrowserNodeSelector.nodeTypes = [ "vtkMRMLSequenceBrowserNode" ]
    self.sequenceBrowserNodeSelector.addEnabled = False
    self.sequenceBrowserNodeSelector.removeEnabled = False
    self.sequenceBrowserNodeSelector.noneEnabled = False
    self.sequenceBrowserNodeSelector.showHidden = False
    self.sequenceBrowserNodeSelector.showChildNodeTypes = False
    self.sequenceBrowserNodeSelector.setMRMLScene( slicer.mrmlScene )
    self.sequenceBrowserNodeSelector.setToolTip( "Select the sequence browser node for playback." )
    self.sequenceLayout.addWidget( self.sequenceBrowserNodeSelector )
    
    self.sequenceBrowserPlayWidget = slicer.qMRMLSequenceBrowserPlayWidget() # TODO: Somehow disable the recording button without changing sequences' recording states
    self.sequenceBrowserPlayWidget.setMRMLSequenceBrowserNode( self.sequenceBrowserNodeSelector.currentNode() )
    self.sequenceLayout.addWidget( self.sequenceBrowserPlayWidget )
    
    self.sequenceBrowserSeekWidget = slicer.qMRMLSequenceBrowserSeekWidget()
    self.sequenceBrowserSeekWidget.setMRMLSequenceBrowserNode( self.sequenceBrowserNodeSelector.currentNode() )
    self.sequenceLayout.addWidget( self.sequenceBrowserSeekWidget )    
    
    
    # Add the playback modes to the tool box
    self.playToolBox.addItem( self.realTimeFrame, "Real-time" )
    self.playToolBox.addItem( self.sequenceFrame, "Sequence" )
    
    #
    # Points group box
    #
    self.pointGroupBox = qt.QGroupBox()
    self.pointGroupBox.setTitle( "Points" )
    self.layout.addWidget( self.pointGroupBox )
    # Layout within the group box
    self.pointGroupBoxLayout = qt.QHBoxLayout( self.pointGroupBox )
    
    # Mark point
    self.markPointButton = qt.QPushButton( "Mark Point" )
    self.markPointButton.setIcon( qt.QIcon( ":/Icons/MarkupsMouseModePlace.png" ) )
    self.markPointButton.setToolTip( "Start placing a point on the ultrasound image." )
    self.pointGroupBoxLayout.addWidget( self.markPointButton )
    
    # Undo
    self.undoPointsButton = qt.QPushButton( "" )
    self.undoPointsButton.setIcon( qt.QIcon( ":/Icons/Small/SlicerUndo.png" ) )
    self.undoPointsButton.setSizePolicy( qt.QSizePolicy.Fixed, qt.QSizePolicy.Fixed )
    self.undoPointsButton.setToolTip( "Remove the most recently placed point." )
    self.pointGroupBoxLayout.addWidget( self.undoPointsButton )
    
    # Reset
    self.resetPointsButton = qt.QPushButton( "" )
    self.resetPointsButton.setIcon( qt.QApplication.style().standardIcon( qt.QStyle.SP_DialogResetButton ) )
    self.resetPointsButton.setSizePolicy( qt.QSizePolicy.Fixed, qt.QSizePolicy.Fixed )
    self.resetPointsButton.setToolTip( "Clear all points." )
    self.pointGroupBoxLayout.addWidget( self.resetPointsButton )
    
    #
    # Result label
    #
    self.calibrationResultLabel = qt.QLabel()
    self.calibrationResultLabel.setText( "No calibration parameters selected." )
    self.calibrationResultLabel.setToolTip( "Output from the calibration." )
    self.layout.addWidget( self.calibrationResultLabel )
    
    
    #
    # Advanced area
    #
    self.advancedCollapsibleButton = ctk.ctkCollapsibleButton()
    self.advancedCollapsibleButton.setText( "Advanced" )
    self.advancedCollapsibleButton.collapsed = True
    self.layout.addWidget( self.advancedCollapsibleButton )
    # Layout within the collapsible button
    self.advancedLayout = qt.QFormLayout( self.advancedCollapsibleButton )
    
    # Mark point
    self.applyButton = qt.QPushButton( "Apply" )
    self.applyButton.setToolTip( "Apply the ImageToProbe transform to the ultrasound image." )
    self.advancedLayout.addWidget( self.applyButton )
    
    
    #
    # Results area
    #
    self.resultsCollapsibleButton = ctk.ctkCollapsibleButton()
    self.resultsCollapsibleButton.setText( "Results" )
    self.resultsCollapsibleButton.collapsed = True
    self.advancedLayout.addWidget( self.resultsCollapsibleButton )
    # Layout within the collapsible button
    self.resultsLayout = qt.QFormLayout( self.resultsCollapsibleButton )
    
    # Results table
    self.resultsTable = qt.QTableWidget( self.resultsCollapsibleButton )
    self.resultsTable.setColumnCount( self.RESULTS_NUM_INDICES )
    self.resultsTable.setHorizontalHeaderLabels( [ "Image Points", "Probe Points", "Error", "Delete" ] )
    self.resultsTable.horizontalHeader().setResizeMode( qt.QHeaderView.Stretch )
    self.resultsTable.horizontalHeader().setResizeMode( self.RESULTS_DELETE_INDEX, qt.QHeaderView.Fixed )
    self.resultsLayout.addRow( self.resultsTable )
    

    #
    # Parameters area
    #
    self.parametersCollapsibleButton = ctk.ctkCollapsibleButton()
    self.parametersCollapsibleButton.setText( "Parameters" )
    self.parametersCollapsibleButton.collapsed = True
    self.advancedLayout.addWidget( self.parametersCollapsibleButton )
    # Layout within the collapsible button
    self.parametersLayout = qt.QVBoxLayout( self.parametersCollapsibleButton )
    
    # Parameters node
    self.frwNodeSelector = slicer.qMRMLNodeComboBox()
    self.frwNodeSelector.nodeTypes = [ "vtkMRMLFiducialRegistrationWizardNode" ]
    self.frwNodeSelector.addEnabled = True
    self.frwNodeSelector.removeEnabled = True
    self.frwNodeSelector.noneEnabled = False
    self.frwNodeSelector.showHidden = False
    self.frwNodeSelector.showChildNodeTypes = False
    self.frwNodeSelector.baseName = "UltrasoundCalibration"
    self.frwNodeSelector.setMRMLScene( slicer.mrmlScene )
    self.frwNodeSelector.setToolTip( "Select the ultrasound calibration parameters node." )
    self.parametersLayout.addWidget( self.frwNodeSelector )
    
    #
    # Input group box
    #
    self.inputGroupBox = qt.QGroupBox( self.parametersCollapsibleButton )
    self.inputGroupBox.setTitle( "Input" )
    self.parametersLayout.addWidget( self.inputGroupBox )
    # Layout within the group box
    self.inputGroupBoxLayout = qt.QFormLayout( self.inputGroupBox )   
    
    # US image selector
    self.usImageNodeSelector = slicer.qMRMLNodeComboBox()
    self.usImageNodeSelector.nodeTypes = [ "vtkMRMLVolumeNode" ]
    self.usImageNodeSelector.addEnabled = False
    self.usImageNodeSelector.removeEnabled = False
    self.usImageNodeSelector.noneEnabled = True
    self.usImageNodeSelector.showHidden = False
    self.usImageNodeSelector.showChildNodeTypes = True
    self.usImageNodeSelector.setMRMLScene( slicer.mrmlScene )
    self.usImageNodeSelector.setToolTip( "Select the ultrasound image node." )
    self.inputGroupBoxLayout.addRow( "Ultrasound image ", self.usImageNodeSelector )
    
    # StylusTipToProbe selector
    self.stylusTipToProbeNodeSelector = slicer.qMRMLNodeComboBox()
    self.stylusTipToProbeNodeSelector.nodeTypes = [ "vtkMRMLLinearTransformNode" ]
    self.stylusTipToProbeNodeSelector.addEnabled = False
    self.stylusTipToProbeNodeSelector.removeEnabled = False
    self.stylusTipToProbeNodeSelector.noneEnabled = True
    self.stylusTipToProbeNodeSelector.showHidden = False
    self.stylusTipToProbeNodeSelector.showChildNodeTypes = True
    self.stylusTipToProbeNodeSelector.setMRMLScene( slicer.mrmlScene )
    self.stylusTipToProbeNodeSelector.setToolTip( "Select the StylusTipToProbe node (parent transforms will be applied)." )
    self.inputGroupBoxLayout.addRow( "StylusTipToProbe ", self.stylusTipToProbeNodeSelector )
    

    #
    # Output group box
    #
    self.outputGroupBox = qt.QGroupBox( self.parametersCollapsibleButton )
    self.outputGroupBox.setTitle( "Output" )
    self.parametersLayout.addWidget( self.outputGroupBox )
    # Layout within the group box
    self.outputGroupBoxLayout = qt.QFormLayout( self.outputGroupBox )
    
    # ImageToProbe selector
    self.imageToProbeNodeSelector = slicer.qMRMLNodeComboBox()
    self.imageToProbeNodeSelector.nodeTypes = [ "vtkMRMLLinearTransformNode" ]
    self.imageToProbeNodeSelector.addEnabled = True
    self.imageToProbeNodeSelector.removeEnabled = False
    self.imageToProbeNodeSelector.noneEnabled = True
    self.imageToProbeNodeSelector.renameEnabled = True
    self.imageToProbeNodeSelector.showHidden = False
    self.imageToProbeNodeSelector.showChildNodeTypes = True
    self.imageToProbeNodeSelector.setMRMLScene( slicer.mrmlScene )
    self.imageToProbeNodeSelector.setToolTip( "Select the ImageToProbe output node (stores the result of the calibration)." )
    self.outputGroupBoxLayout.addRow( "ImageToProbe ", self.imageToProbeNodeSelector )
    


    #
    # Set up connections
    #
    self.freezeButton.connect( "clicked(bool)", self.onFreezeButtonClicked )
    self.sequenceBrowserNodeSelector.connect( "currentNodeChanged(vtkMRMLNode*)", self.onSequenceBrowserNodeChanged )
    
    self.frwNodeSelector.connect( "currentNodeChanged(vtkMRMLNode*)", self.onCalibrationNodeChanged )
    self.usImageNodeSelector.connect( "currentNodeChanged(vtkMRMLNode*)", self.onUSImageNodeChanged )
    self.stylusTipToProbeNodeSelector.connect( "currentNodeChanged(vtkMRMLNode*)", self.onStylusTipToProbeNodeChanged )
    
    self.markPointButton.connect( "clicked(bool)", self.onMarkPointButtonClicked )
    self.undoPointsButton.connect( "clicked(bool)", self.onUndoPointsButtonClicked )
    self.resetPointsButton.connect( "clicked(bool)", self.onResetPointsButtonClicked )

    self.imageToProbeNodeSelector.connect( "currentNodeChanged(vtkMRMLNode*)", self.onImageToProbeNodeChanged )
    
    self.applyButton.connect( "clicked(bool)", self.onApplyOutputTransformToImageClicked )
    
    
    #
    # Create a parameters node by default
    #
    defaultFRWNode = slicer.vtkMRMLFiducialRegistrationWizardNode()
    defaultFRWNode.SetName( "UltrasoundCalibration" )
    defaultFRWNode.SetScene( slicer.mrmlScene )
    slicer.mrmlScene.AddNode( defaultFRWNode )    
    self.frwNodeSelector.setCurrentNodeID( defaultFRWNode.GetID() )

    
    
    # Add vertical spacer
    self.layout.addStretch(1)
    

  def cleanup( self ):
    pass
    
  def resetSelectors( self, frwNode, eventid ):
    # Update the selectors so nothing is selected
    if ( frwNode is None ):
      self.usImageNodeSelector.setCurrentNodeID( "" )
      self.stylusTipToProbeNodeSelector.setCurrentNodeID( "" )
      self.imageToProbeNodeSelector.setCurrentNodeID( "" )
      return

    if ( frwNode.GetNodeReference( self.ULTRASOUND_IMAGE_ROLE ) is not None ):    
      self.usImageNodeSelector.setCurrentNode( frwNode.GetNodeReference( self.ULTRASOUND_IMAGE_ROLE ) )      
    
    if ( frwNode.GetProbeTransformToNode() is not None ):
      self.stylusTipToProbeNodeSelector.setCurrentNode( frwNode.GetProbeTransformToNode() )

    if ( frwNode.GetOutputTransformNode() is not None ):
      self.imageToProbeNodeSelector.setCurrentNode( frwNode.GetOutputTransformNode() )
      
      
  def guessParameters( self ):
    frwNode = self.frwNodeSelector.currentNode()    
    if ( frwNode is None ):
      return
      
    # Use guess prefixes to guess what the node is
    if ( frwNode.GetNodeReference( self.ULTRASOUND_IMAGE_ROLE ) is None ):
      guessNode = self.pbucLogic.GetFirstNodeByClassByPrefix( "vtkMRMLVolumeNode", self.IMAGE_PREFIX_GUESS )
      self.usImageNodeSelector.setCurrentNode( guessNode )
    
    if ( frwNode.GetProbeTransformToNode() is None ):
      guessNode = self.pbucLogic.GetFirstNodeByClassByPrefix( "vtkMRMLLinearTransformNode", self.STYLUSTIP_TO_PROBE_PREFIX_GUESS )
      self.stylusTipToProbeNodeSelector.setCurrentNode( guessNode )
    if ( frwNode.GetOutputTransformNode() is None ):
      guessNode = self.pbucLogic.GetFirstNodeByClassByPrefix( "vtkMRMLLinearTransformNode", self.IMAGE_TO_PROBE_PREFIX_GUESS )
      self.imageToProbeNodeSelector.setCurrentNode( guessNode ) 
    

  def onFreezeButtonClicked( self ):
    self.pbucLogic.FreezeConnection( self.connectorNodeSelector.currentNode() )
    
  def onSequenceBrowserNodeChanged( self ):
    sbNode = self.sequenceBrowserNodeSelector.currentNode()
    
    self.sequenceBrowserPlayWidget.setMRMLSequenceBrowserNode( sbNode )
    self.sequenceBrowserSeekWidget.setMRMLSequenceBrowserNode( sbNode )
    
    if ( sbNode is not None ):
      sbNode.SetRecording( None, False )
    
  def onCalibrationNodeChanged( self ):
    frwNode = self.frwNodeSelector.currentNode()
  
    self.pbucLogic.SetupCalibrationNode( frwNode )
    self.guessParameters()
    
    # Observe changes so we can update the output
    if ( frwNode is not None ):
      frwNode.AddObserver( vtk.vtkCommand.ModifiedEvent, self.onCalibrationOutputChanged )
      frwNode.AddObserver( vtk.vtkCommand.ModifiedEvent, self.resetSelectors )
      
    self.onCalibrationOutputChanged( frwNode, None )
    self.resetSelectors( frwNode, None )
    
  def onUSImageNodeChanged( self ):
    self.pbucLogic.SetupImageNodeForCalibration( self.usImageNodeSelector.currentNode() )
    
    frwNode = self.frwNodeSelector.currentNode()
    if ( frwNode is not None ):
      frwNode.SetAndObserveNodeReferenceID( self.ULTRASOUND_IMAGE_ROLE, self.usImageNodeSelector.currentNodeID )
    
  def onStylusTipToProbeNodeChanged( self ):
    self.pbucLogic.SetStylusTipToProbeTransform( self.stylusTipToProbeNodeSelector.currentNode(), self.frwNodeSelector.currentNode() )
    
  def onMarkPointButtonClicked( self ):
    self.pbucLogic.StartMarkPoint( self.frwNodeSelector.currentNode() )
    
  def onUndoPointsButtonClicked( self ):
    self.pbucLogic.UndoPoints( self.frwNodeSelector.currentNode() )
    
  def onResetPointsButtonClicked( self ):
    self.pbucLogic.ResetPoints( self.frwNodeSelector.currentNode() )
    
  def onImageToProbeNodeChanged( self ):
    self.pbucLogic.SetImageToProbeTransform( self.imageToProbeNodeSelector.currentNode(), self.frwNodeSelector.currentNode() )
    
  def onCalibrationOutputChanged( self, frwNode, eventid ):
    frwLogic = slicer.modules.fiducialregistrationwizard.logic()
    if ( frwLogic is None ):
      return
      
    self.calibrationResultLabel.setText( frwLogic.GetOutputMessage( self.frwNodeSelector.currentNodeID ) )
    
    errorList = self.pbucLogic.ComputeErrors( frwNode )
    self.updateResultsTable( errorList )
    
  def onApplyOutputTransformToImageClicked( self ):
    self.pbucLogic.ApplyTransformToImage( self.frwNodeSelector.currentNode() )
    
  def updateResultsTable( self, errorList ):
    self.resultsTable.setRowCount( len( errorList ) )
    
    for i in range( len( errorList ) ):
      errorElement = errorList[ i ]
    
      fromItem = qt.QTableWidgetItem( errorElement[ self.RESULTS_IMAGE_POINTS_INDEX ] )
      self.resultsTable.setItem( i, self.RESULTS_IMAGE_POINTS_INDEX, fromItem )
      toItem = qt.QTableWidgetItem( errorElement[ self.RESULTS_PROBE_POINTS_INDEX ] )
      self.resultsTable.setItem( i, self.RESULTS_PROBE_POINTS_INDEX, toItem )
      errorItem = qt.QTableWidgetItem( str( round( errorElement[ self.RESULTS_ERROR_INDEX ], 2 ) ) )
      self.resultsTable.setItem( i, self.RESULTS_ERROR_INDEX, errorItem )
      
      deleteButton = qt.QPushButton()
      deleteButton.setIcon( slicer.app.style().standardIcon( qt.QStyle.SP_DialogDiscardButton ) )
      deleteButton.connect( "clicked()", partial( self.pbucLogic.DeleteNthPoint, self.frwNodeSelector.currentNode(), i ) )
      self.resultsTable.setCellWidget( i, self.RESULTS_DELETE_INDEX, deleteButton )
      
      




#
# PointerBasedUSCalibrationLogic
#

class PointerBasedUSCalibrationLogic(ScriptedLoadableModuleLogic):
  """This class should implement all the actual
  computation done by your module.  The interface
  should be such that other python code can import
  this class and make use of the functionality without
  requiring an instance of the Widget.
  Uses ScriptedLoadableModuleLogic base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """
  
  US_CALIBRATION_SLICE_VIEWER_NAME = "Red"

  def FreezeConnection( self, connectorNode ):
    if ( connectorNode is None ):
      return
      
    if ( connectorNode.GetState() == slicer.vtkMRMLIGTLConnectorNode.STATE_OFF ):
      connectorNode.Start()
    else:
      connectorNode.Stop()
      

  def SetupCalibrationNode( self, frwNode ):
    if ( frwNode is None ):
      return
      
    # Add a new fiducial node for "Image_Points" (from points)
    if ( frwNode.GetFromFiducialListNode() is None ):
      imagePoints = slicer.vtkMRMLMarkupsFiducialNode()
      imagePoints.SetName( "Image_Points" )
      imagePoints.SetScene( slicer.mrmlScene )
      slicer.mrmlScene.AddNode( imagePoints )
      frwNode.SetAndObserveFromFiducialListNodeId( imagePoints.GetID() )
      
    # Add a new fiducial node for "Probe_Points" (to points)
    if ( frwNode.GetToFiducialListNode() is None ):
      probePoints = slicer.vtkMRMLMarkupsFiducialNode()
      probePoints.SetName( "Probe_Points" )
      probePoints.SetScene( slicer.mrmlScene )
      slicer.mrmlScene.AddNode( probePoints )
      frwNode.SetAndObserveToFiducialListNodeId( probePoints.GetID() )
      
    frwNode.SetRegistrationModeToSimilarity()
    
    # Observe Markups node for knowing when to add corresponding point
    frwNode.GetFromFiducialListNode().AddObserver( slicer.vtkMRMLMarkupsFiducialNode.MarkupAddedEvent, partial( self.AddPointToCalibration, frwNode ) )
  
  
  def SetupImageNodeForCalibration( self, usImageNode ):
    if ( usImageNode is None ):
      return
      
    layoutManager = slicer.app.layoutManager()
    sliceWidget = layoutManager.sliceWidget( self.US_CALIBRATION_SLICE_VIEWER_NAME )
    sliceLogic = sliceWidget.sliceLogic()
    
    # Set up the volume reslice driver
    vrdLogic = slicer.modules.volumereslicedriver.logic()
    if ( vrdLogic is None ):
      logging.warning( "Could not find logic for Volume Reslice Driver" )
      return
      
    sliceNode = sliceWidget.sliceView().mrmlSliceNode()    
    sliceNode.SetSliceResolutionMode( slicer.vtkMRMLSliceNode.SliceFOVMatchVolumesSpacingMatch2DView )
    
    vrdLogic.SetDriverForSlice( usImageNode.GetID(), sliceNode )
    vrdLogic.SetModeForSlice( vrdLogic.MODE_TRANSVERSE, sliceNode )
    vrdLogic.SetFlipForSlice( True, sliceNode )
    vrdLogic.SetRotationForSlice( 0, sliceNode )
    
    # Set the layout to show only the image view
    layoutManager.setLayout( slicer.vtkMRMLLayoutNode.SlicerLayoutOneUpRedSliceView )
    
    # Set the image to display in the slice viewer
    sliceLogic.GetSliceCompositeNode().SetBackgroundVolumeID( usImageNode.GetID() )
    
    # Expand the image to fit the slice viewer
    sliceWidget.sliceController().fitSliceToBackground()
    
 
  def SetStylusTipToProbeTransform( self, stylusTipToProbeNode, frwNode ):
    if ( frwNode is None or stylusTipToProbeNode is None ):
      return 
     
    frwNode.SetProbeTransformToNodeId( stylusTipToProbeNode.GetID() )
    
     
  def StartMarkPoint( self, frwNode ):
    if ( frwNode is None or frwNode.GetFromFiducialListNode() is None ):
      return 
     
    selectionNode = slicer.app.applicationLogic().GetSelectionNode()
    interactionNode = slicer.app.applicationLogic().GetInteractionNode()
    if ( selectionNode is None and interactionNode is None ):
      logging.warning( "Could not find selection node or interaction node" )
      return
    
    selectionNode.SetActivePlaceNodeID( frwNode.GetFromFiducialListNode().GetID() )
    interactionNode.SetCurrentInteractionMode( interactionNode.Place )
    
    
  def UndoPoints( self, frwNode ):
    if ( frwNode is None ):
      return
      
    fromFiducialList = frwNode.GetFromFiducialListNode()
    toFiducialList = frwNode.GetToFiducialListNode()
    if ( fromFiducialList is None or toFiducialList is None ):
      return
     
    # Remove the most recently added point from each fiducial list
    if ( fromFiducialList.GetNumberOfFiducials() > 0 ):
      fromFiducialList.RemoveMarkup( fromFiducialList.GetNumberOfFiducials() - 1 )
     
    if ( toFiducialList.GetNumberOfFiducials() > 0 ):
      toFiducialList.RemoveMarkup( toFiducialList.GetNumberOfFiducials() - 1 )
      
      
  def ResetPoints( self, frwNode ):
    if ( frwNode is None ):
      return
      
    fromFiducialList = frwNode.GetFromFiducialListNode()
    toFiducialList = frwNode.GetToFiducialListNode()
    if ( fromFiducialList is None or toFiducialList is None ):
      return
     
    fromFiducialList.RemoveAllMarkups()
    toFiducialList.RemoveAllMarkups()
    
    
  def SetImageToProbeTransform( self, imageToProbeNode, frwNode ):
    if ( frwNode is None or imageToProbeNode is None ):
      return 
     
    frwNode.SetOutputTransformNodeId( imageToProbeNode.GetID() )


  def AddPointToCalibration( self, frwNode, addedFiducialList, eventid ):
    if ( frwNode is None ):
      return
      
    # Add a point to whatever list was not justed added to   
    fiducialListToAddPoint = None
    if ( addedFiducialList is frwNode.GetFromFiducialListNode() ):
      fiducialListToAddPoint = frwNode.GetToFiducialListNode()
    if ( addedFiducialList is frwNode.GetToFiducialListNode() ):
      fiducialListToAddPoint = frwNode.GetFromFiducialListNode()
      
    if ( fiducialListToAddPoint is None ):
      return
      
    frwLogic = slicer.modules.fiducialregistrationwizard.logic()
    if ( frwLogic is None ):
      return
      
    if ( addedFiducialList.GetNumberOfFiducials() - fiducialListToAddPoint.GetNumberOfFiducials() != 1 ):
      logging.warning( "Image and probe points lists have become unsynchronized." )      
      return
      
    frwLogic.AddFiducial( frwNode.GetProbeTransformToNode(), fiducialListToAddPoint )
    
    
  def DeleteNthPoint( self, frwNode, n ):
    if ( frwNode is None ):
      return
      
    fromFiducialList = frwNode.GetFromFiducialListNode()
    toFiducialList = frwNode.GetToFiducialListNode()
    if ( fromFiducialList is None or toFiducialList is None ):
      return
     
    # Remove the most recently added point from each fiducial list
    if ( fromFiducialList.GetNumberOfFiducials() > n ):
      fromFiducialList.RemoveMarkup( n )
     
    if ( toFiducialList.GetNumberOfFiducials() > n ):
      toFiducialList.RemoveMarkup( n )
      
      
  def GetFirstNodeByClassByPrefix( self, className, prefixes ):
    nodeCollection = slicer.mrmlScene.GetNodesByClass( className )
    
    for i in range( nodeCollection.GetNumberOfItems() ):
      currNode = nodeCollection.GetItemAsObject( i )
      for prefix in prefixes:
        if prefix in currNode.GetName():
          return currNode
        
    return None
    
    
  def ApplyTransformToImage( self, frwNode ):
    if ( frwNode is None ):
      return
      
    print "Applying"
      
    imageToProbeTransformNode = frwNode.GetOutputTransformNode()
    usImageNode = frwNode.GetNodeReference( PointerBasedUSCalibrationWidget.ULTRASOUND_IMAGE_ROLE )
    if ( imageToProbeTransformNode is None or usImageNode is None ):
      return
      
    # Toggle whether the image is under the image to probe transform
    if ( usImageNode.GetTransformNodeID() == imageToProbeTransformNode.GetID() ):
      usImageNode.SetAndObserveTransformNodeID( "" )
    else:
      usImageNode.SetAndObserveTransformNodeID( imageToProbeTransformNode.GetID() )
    
    
  def ComputeErrors( self, frwNode ):
    if ( frwNode is None ):
      return []
      
    fromFiducialList = frwNode.GetFromFiducialListNode()
    toFiducialList = frwNode.GetToFiducialListNode()
    outputTransform = frwNode.GetOutputTransformNode()
    if ( fromFiducialList is None or toFiducialList is None or outputTransform is None ):
      return []
      
    outputMatrix = vtk.vtkMatrix4x4()
    outputTransform.GetMatrixTransformToParent( outputMatrix )
      
    maxNumFiducials = max( fromFiducialList.GetNumberOfFiducials(), toFiducialList.GetNumberOfFiducials() )
    if ( fromFiducialList.GetNumberOfFiducials() != toFiducialList.GetNumberOfFiducials() or maxNumFiducials < 3 ):
      return []

    errorList = []
    for i in range( maxNumFiducials ):
      errorElement = [ "", "", "" ]
    
      if ( fromFiducialList.GetNumberOfFiducials() > i ):
        errorElement[ PointerBasedUSCalibrationWidget.RESULTS_IMAGE_POINTS_INDEX ] = fromFiducialList.GetNthFiducialLabel( i )
        
      if ( toFiducialList.GetNumberOfFiducials() > i ):
        errorElement[ PointerBasedUSCalibrationWidget.RESULTS_PROBE_POINTS_INDEX ] = toFiducialList.GetNthFiducialLabel( i )
        
      if ( fromFiducialList.GetNumberOfFiducials() > i and toFiducialList.GetNumberOfFiducials() > i ):   
        currFromPoint = [ 0, 0, 0 ]
        fromFiducialList.GetNthFiducialPosition( i, currFromPoint )
        currFromPoint.append( 1 )
      
        currToPoint = [ 0, 0, 0 ]
        toFiducialList.GetNthFiducialPosition( i, currToPoint )
      
        currTransformedFromPoint = [ 0, 0, 0, 1 ]
        outputMatrix.MultiplyPoint( currFromPoint, currTransformedFromPoint )
        currTransformedFromPoint = currTransformedFromPoint[:3] 
      
        currError = math.sqrt( vtk.vtkMath.Distance2BetweenPoints( currToPoint, currTransformedFromPoint ) )
        errorElement[ PointerBasedUSCalibrationWidget.RESULTS_ERROR_INDEX ] = currError
      
      errorList.append( errorElement )
      
    return errorList
      
      



class PointerBasedUSCalibrationTest(ScriptedLoadableModuleTest):
  """
  This is the test case for your scripted module.
  Uses ScriptedLoadableModuleTest base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def setUp(self):
    """ Do whatever is needed to reset the state - typically a scene clear will be enough.
    """
    slicer.mrmlScene.Clear(0)

  def runTest(self):
    """Run as few or as many tests as needed here.
    """
    self.setUp()
    self.test_PointerBasedUSCalibration1()

  def test_PointerBasedUSCalibration1(self):
    """ Ideally you should have several levels of tests.  At the lowest level
    tests should exercise the functionality of the logic with different inputs
    (both valid and invalid).  At higher levels your tests should emulate the
    way the user would interact with your code and confirm that it still works
    the way you intended.
    One of the most important features of the tests is that it should alert other
    developers when their changes will have an impact on the behavior of your
    module.  For example, if a developer removes a feature that you depend on,
    your test should break so they know that the feature is needed.
    """

    self.delayDisplay("Starting the test")
    #
    # first, get some data
    #
    import urllib
    downloads = (
        ('http://slicer.kitware.com/midas3/download?items=5767', 'FA.nrrd', slicer.util.loadVolume),
        )

    for url,name,loader in downloads:
      filePath = slicer.app.temporaryPath + '/' + name
      if not os.path.exists(filePath) or os.stat(filePath).st_size == 0:
        logging.info('Requesting download %s from %s...\n' % (name, url))
        urllib.urlretrieve(url, filePath)
      if loader:
        logging.info('Loading %s...' % (name,))
        loader(filePath)
    self.delayDisplay('Finished with download and loading')

    volumeNode = slicer.util.getNode(pattern="FA")
    logic = PointerBasedUSCalibrationLogic()
    self.assertIsNotNone( logic.hasImageData(volumeNode) )
    self.delayDisplay('Test passed!')
