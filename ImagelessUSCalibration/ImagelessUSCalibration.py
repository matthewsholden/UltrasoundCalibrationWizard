import os
import unittest
import math
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
import logging
from functools import partial

#
# ImagelessUSCalibration
#

class ImagelessUSCalibration(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "Imageless US Calibration" # TODO make this more human readable by adding spaces
    self.parent.categories = ["IGT"]
    self.parent.dependencies = []
    self.parent.contributors = ["Matthew S. Holden (PerkLab, Queen's University)"] # replace with "Firstname Lastname (Organization)"
    self.parent.helpText = """
    This module is intended for calibrating an ultrasound probe using only the physical characteristics of the ultrasound probe.
    This method is not particularly accurate, but is fast and easy.
    """
    self.parent.acknowledgementText = """
    This file was originally developed by Matthew S. Holden, PerkLab, Queen's University and was supported by OCAIRO, NSERC, and CIHR.
    """ # replace with organization, grant and thanks.

#
# ImagelessUSCalibrationWidget
#

class ImagelessUSCalibrationWidget(ScriptedLoadableModuleWidget):
  """Uses ScriptedLoadableModuleWidget base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """
  
  IMAGE_PREFIX_GUESS = [ "Image_" ]
  STYLUSTIP_TO_PROBE_PREFIX_GUESS = [ "StylusTipTo", "NeedleTipTo" ]
  IMAGE_TO_PROBE_PREFIX_GUESS = [ "ImageToProbe" ]
  
  STYLUSTIP_TO_PROBE_TRANSFORM_ROLE = "StylusTipToProbeTransform"
  IMAGE_TO_PROBE_TRANSFORM_ROLE = "ImageToProbeTransform"
  ULTRASOUND_IMAGE_ROLE = "UltrasoundImage"
  
  MARKED_POINTS_ROLE = "MarkedPoints"
  UNMARKED_POINTS_ROLE = "UnmarkedPoints"
  
  DEPTH_ROLE = "Depth"
  
  OUTPUT_MESSAGE_ROLE = "OutputMessage"

  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)
    
    # Instantiate and connect widgets ...
    self.pbucLogic = ImagelessUSCalibrationLogic() # Have reference to an instance of the logic   

    
    #
    # Points group box
    #
    self.pointGroupBox = qt.QGroupBox()
    self.pointGroupBox.setTitle( "Points" )
    self.layout.addWidget( self.pointGroupBox )
    # Layout within the group box
    self.pointGroupBoxLayout = qt.QVBoxLayout( self.pointGroupBox )
    
    # Marked point frame
    self.markedPointFrame = qt.QFrame()
    self.pointGroupBoxLayout.addWidget( self.markedPointFrame )
    # Layout within the frame
    self.markedPointLayout = qt.QHBoxLayout( self.markedPointFrame )
    
    # Select point
    self.selectMarkedPointButton = qt.QPushButton( "Marked corner" )
    self.selectMarkedPointButton.setIcon( qt.QIcon( ":/Icons/MarkupsMouseModePlace.png" ) )
    self.selectMarkedPointButton.setToolTip( "Place points on the corners of the ultrasound probe's foot on the marked side." )
    self.markedPointLayout.addWidget( self.selectMarkedPointButton )
    
    # Reset
    self.resetMarkedPointsButton = qt.QPushButton( "" )
    self.resetMarkedPointsButton.setIcon( qt.QApplication.style().standardIcon( qt.QStyle.SP_DialogResetButton ) )
    self.resetMarkedPointsButton.setSizePolicy( qt.QSizePolicy.Fixed, qt.QSizePolicy.Fixed )
    self.resetMarkedPointsButton.setToolTip( "Clear all points." )
    self.markedPointLayout.addWidget( self.resetMarkedPointsButton )
    
    # Unmarked point frame
    self.unmarkedPointFrame = qt.QFrame()
    self.pointGroupBoxLayout.addWidget( self.unmarkedPointFrame )
    # Layout within the frame
    self.unmarkedPointLayout = qt.QHBoxLayout( self.unmarkedPointFrame )
    
    # Select point
    self.selectUnmarkedPointButton = qt.QPushButton( "Unmarked corner" )
    self.selectUnmarkedPointButton.setIcon( qt.QIcon( ":/Icons/MarkupsMouseModePlace.png" ) )
    self.selectUnmarkedPointButton.setToolTip( "Place points on the corners of the ultrasound probe's foot on the unmarked side." )
    self.unmarkedPointLayout.addWidget( self.selectUnmarkedPointButton )
    
    # Reset
    self.resetUnmarkedPointsButton = qt.QPushButton( "" )
    self.resetUnmarkedPointsButton.setIcon( qt.QApplication.style().standardIcon( qt.QStyle.SP_DialogResetButton ) )
    self.resetUnmarkedPointsButton.setSizePolicy( qt.QSizePolicy.Fixed, qt.QSizePolicy.Fixed )
    self.resetUnmarkedPointsButton.setToolTip( "Clear all points." )
    self.unmarkedPointLayout.addWidget( self.resetUnmarkedPointsButton )
    
    #
    # Depth group box
    #
    self.depthGroupBox = qt.QGroupBox()
    self.depthGroupBox.setTitle( "Depth" )
    self.layout.addWidget( self.depthGroupBox )
    # Layout within the group box
    self.depthGroupBoxLayout = qt.QHBoxLayout( self.depthGroupBox )
    
    # Depth label
    self.depthLabel = qt.QLabel( "Depth \t" )
    self.depthLabel.setSizePolicy( qt.QSizePolicy.Fixed, qt.QSizePolicy.Fixed )
    self.depthGroupBoxLayout.addWidget( self.depthLabel )
    
    # Depth spin box
    self.depthSpinBox = qt.QSpinBox()
    self.depthSpinBox.setRange( 0, 1000 )
    self.depthSpinBox.setSingleStep( 1 )
    self.depthSpinBox.setSuffix( "mm" )
    self.depthSpinBox.setToolTip( "Ultrasound imaging depth." )
    self.depthGroupBoxLayout.addWidget( self.depthSpinBox )
        
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
    # Parameters area
    #
    self.parametersCollapsibleButton = ctk.ctkCollapsibleButton()
    self.parametersCollapsibleButton.setText( "Parameters" )
    self.parametersCollapsibleButton.collapsed = True
    self.advancedLayout.addWidget( self.parametersCollapsibleButton )
    # Layout within the collapsible button
    self.parametersLayout = qt.QVBoxLayout( self.parametersCollapsibleButton )
    
    # Parameters node
    self.usCalibrationNodeSelector = slicer.qMRMLNodeComboBox()
    self.usCalibrationNodeSelector.nodeTypes = [ "vtkMRMLScriptedModuleNode" ]
    self.usCalibrationNodeSelector.addEnabled = True
    self.usCalibrationNodeSelector.removeEnabled = True
    self.usCalibrationNodeSelector.noneEnabled = False
    self.usCalibrationNodeSelector.showHidden = True # Since scripted module nodes are hidden by default
    self.usCalibrationNodeSelector.showChildNodeTypes = False
    self.usCalibrationNodeSelector.baseName = "UltrasoundCalibration"
    self.usCalibrationNodeSelector.setMRMLScene( slicer.mrmlScene )
    self.usCalibrationNodeSelector.setToolTip( "Select the ultrasound calibration parameters node." )
    self.parametersLayout.addWidget( self.usCalibrationNodeSelector )
    
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
    self.selectMarkedPointButton.connect( "clicked(bool)", self.onSelectMarkedPointButtonClicked )
    self.resetMarkedPointsButton.connect( "clicked(bool)", self.onResetMarkedPointsButtonClicked )
    
    self.selectUnmarkedPointButton.connect( "clicked(bool)", self.onSelectUnmarkedPointButtonClicked )
    self.resetUnmarkedPointsButton.connect( "clicked(bool)", self.onResetUnmarkedPointsButtonClicked )
    
    self.depthSpinBox.connect( "valueChanged(int)", self.onDepthChanged )

    self.usCalibrationNodeSelector.connect( "currentNodeChanged(vtkMRMLNode*)", self.onCalibrationNodeChanged )    
    self.usImageNodeSelector.connect( "currentNodeChanged(vtkMRMLNode*)", self.onUSImageNodeChanged )
    self.stylusTipToProbeNodeSelector.connect( "currentNodeChanged(vtkMRMLNode*)", self.onStylusTipToProbeNodeChanged )
    
    self.imageToProbeNodeSelector.connect( "currentNodeChanged(vtkMRMLNode*)", self.onImageToProbeNodeChanged )
    
    self.applyButton.connect( "clicked(bool)", self.onApplyOutputTransformToImageClicked )
    
    
    #
    # Create a parameters node by default
    #
    defaultUSCalibrationNode = slicer.vtkMRMLScriptedModuleNode()
    defaultUSCalibrationNode.SetName( "UltrasoundCalibration" )
    defaultUSCalibrationNode.SetScene( slicer.mrmlScene )
    slicer.mrmlScene.AddNode( defaultUSCalibrationNode )    
    self.usCalibrationNodeSelector.setCurrentNodeID( defaultUSCalibrationNode.GetID() )

    
    
    # Add vertical spacer
    self.layout.addStretch(1)
    

  def cleanup( self ):
    pass
    
  def resetSelectors( self, usCalibrationNode, eventid ):
    # Update the selectors so nothing is selected
    if ( usCalibrationNode is None ):
      self.usImageNodeSelector.setCurrentNodeID( "" )
      self.stylusTipToProbeNodeSelector.setCurrentNodeID( "" )
      self.imageToProbeNodeSelector.setCurrentNodeID( "" )
      self.depthSpinBox.setValue( 0 )
      return

    if ( usCalibrationNode.GetNodeReference( self.ULTRASOUND_IMAGE_ROLE ) is not None ):    
      self.usImageNodeSelector.setCurrentNode( usCalibrationNode.GetNodeReference( self.ULTRASOUND_IMAGE_ROLE ) )      
    
    if ( usCalibrationNode.GetNodeReference( self.STYLUSTIP_TO_PROBE_TRANSFORM_ROLE ) is not None ):
      self.stylusTipToProbeNodeSelector.setCurrentNode( usCalibrationNode.GetNodeReference( self.STYLUSTIP_TO_PROBE_TRANSFORM_ROLE ) )

    if ( usCalibrationNode.GetNodeReference( self.IMAGE_TO_PROBE_TRANSFORM_ROLE ) is not None ):
      self.imageToProbeNodeSelector.setCurrentNode( usCalibrationNode.GetNodeReference( self.IMAGE_TO_PROBE_TRANSFORM_ROLE ) )
      
    try:
      depth = float( usCalibrationNode.GetAttribute( self.DEPTH_ROLE ) )
      self.depthSpinBox.setValue( depth )
    except:
      pass
      
    self.calibrationResultLabel.setText( usCalibrationNode.GetAttribute( self.OUTPUT_MESSAGE_ROLE ) )
      
      
  def guessParameters( self ):
    usCalibrationNode = self.usCalibrationNodeSelector.currentNode()    
    if ( usCalibrationNode is None ):
      return
      
    # Use guess prefixes to guess what the node is
    if ( usCalibrationNode.GetNodeReference( self.ULTRASOUND_IMAGE_ROLE ) is None ):
      guessNode = self.pbucLogic.GetFirstNodeByClassByPrefix( "vtkMRMLVolumeNode", self.IMAGE_PREFIX_GUESS )
      self.usImageNodeSelector.setCurrentNode( None )
      self.usImageNodeSelector.setCurrentNode( guessNode )
    
    if ( usCalibrationNode.GetNodeReference( self.STYLUSTIP_TO_PROBE_TRANSFORM_ROLE ) is None ):
      guessNode = self.pbucLogic.GetFirstNodeByClassByPrefix( "vtkMRMLLinearTransformNode", self.STYLUSTIP_TO_PROBE_PREFIX_GUESS )
      self.stylusTipToProbeNodeSelector.setCurrentNode( None )
      self.stylusTipToProbeNodeSelector.setCurrentNode( guessNode )
    if ( usCalibrationNode.GetNodeReference( self.IMAGE_TO_PROBE_TRANSFORM_ROLE ) is None ):
      guessNode = self.pbucLogic.GetFirstNodeByClassByPrefix( "vtkMRMLLinearTransformNode", self.IMAGE_TO_PROBE_PREFIX_GUESS )
      self.imageToProbeNodeSelector.setCurrentNode( None )
      self.imageToProbeNodeSelector.setCurrentNode( guessNode )

    
  def onCalibrationNodeChanged( self ):
    usCalibrationNode = self.usCalibrationNodeSelector.currentNode()
  
    self.pbucLogic.SetupCalibrationNode( usCalibrationNode )
    self.guessParameters()
    
    # Observe changes so we can update the output
    if ( usCalibrationNode is not None ):
      usCalibrationNode.AddObserver( vtk.vtkCommand.ModifiedEvent, self.onCalibrationOutputChanged )
      usCalibrationNode.AddObserver( vtk.vtkCommand.ModifiedEvent, self.resetSelectors )
      
    self.onCalibrationOutputChanged( usCalibrationNode, None )
    self.resetSelectors( usCalibrationNode, None )
    
  def onUSImageNodeChanged( self ):
    self.pbucLogic.SetupImageNodeForCalibration( self.usImageNodeSelector.currentNode() )
    
    usCalibrationNode = self.usCalibrationNodeSelector.currentNode()
    if ( usCalibrationNode is not None ):
      usCalibrationNode.SetAndObserveNodeReferenceID( self.ULTRASOUND_IMAGE_ROLE, self.usImageNodeSelector.currentNodeID )
    
  def onStylusTipToProbeNodeChanged( self ):
    self.pbucLogic.SetStylusTipToProbeTransform( self.stylusTipToProbeNodeSelector.currentNode(), self.usCalibrationNodeSelector.currentNode() )
    
  def onSelectMarkedPointButtonClicked( self ):
    self.pbucLogic.SelectMarkedPoint( self.usCalibrationNodeSelector.currentNode() )
    
  def onResetMarkedPointsButtonClicked( self ):
    self.pbucLogic.ResetMarkedPoints( self.usCalibrationNodeSelector.currentNode() )
    
  def onSelectUnmarkedPointButtonClicked( self ):
    self.pbucLogic.SelectUnmarkedPoint( self.usCalibrationNodeSelector.currentNode() )
    
  def onResetUnmarkedPointsButtonClicked( self ):
    self.pbucLogic.ResetUnmarkedPoints( self.usCalibrationNodeSelector.currentNode() )
    
  def onDepthChanged( self ):
    self.pbucLogic.SetDepth( self.depthSpinBox.value, self.usCalibrationNodeSelector.currentNode() )
    
  def onImageToProbeNodeChanged( self ):
    self.pbucLogic.SetImageToProbeTransform( self.imageToProbeNodeSelector.currentNode(), self.usCalibrationNodeSelector.currentNode() )
    
  def onCalibrationOutputChanged( self, usCalibrationNode, eventid ):
    if ( usCalibrationNode is None ):
      return
    
    self.calibrationResultLabel.setText( usCalibrationNode.GetAttribute( self.OUTPUT_MESSAGE_ROLE ) )
    
  def onApplyOutputTransformToImageClicked( self ):
    self.pbucLogic.ApplyTransformToImage( self.usCalibrationNodeSelector.currentNode() )




#
# ImagelessUSCalibrationLogic
#

class ImagelessUSCalibrationLogic(ScriptedLoadableModuleLogic):
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
      

  def SetupCalibrationNode( self, usCalibrationNode ):
    if ( usCalibrationNode is None ):
      return

    # Reference to marked points lists
    if ( usCalibrationNode.GetNodeReference( ImagelessUSCalibrationWidget.MARKED_POINTS_ROLE ) is None ):
      markedPoints = slicer.vtkMRMLMarkupsFiducialNode()
      markedPoints.SetName( "Marked_Points" )
      markedPoints.SetScene( slicer.mrmlScene )
      slicer.mrmlScene.AddNode( markedPoints )
      usCalibrationNode.SetAndObserveNodeReferenceID( ImagelessUSCalibrationWidget.MARKED_POINTS_ROLE, markedPoints.GetID() )
      
    # Reference to unmarked points lists
    if ( usCalibrationNode.GetNodeReference( ImagelessUSCalibrationWidget.UNMARKED_POINTS_ROLE ) is None ):
      unmarkedPoints = slicer.vtkMRMLMarkupsFiducialNode()
      unmarkedPoints.SetName( "Unmarked_Points" )
      unmarkedPoints.SetScene( slicer.mrmlScene )
      slicer.mrmlScene.AddNode( unmarkedPoints )
      usCalibrationNode.SetAndObserveNodeReferenceID( ImagelessUSCalibrationWidget.UNMARKED_POINTS_ROLE, unmarkedPoints.GetID() )
    
    # Observe Markups node for knowing when to add corresponding point
    usCalibrationNode.GetNodeReference( ImagelessUSCalibrationWidget.UNMARKED_POINTS_ROLE ).AddObserver( vtk.vtkCommand.ModifiedEvent, partial( self.ComputeCalibration, usCalibrationNode ) )
    usCalibrationNode.GetNodeReference( ImagelessUSCalibrationWidget.MARKED_POINTS_ROLE ).AddObserver( vtk.vtkCommand.ModifiedEvent, partial( self.ComputeCalibration, usCalibrationNode ) )
    usCalibrationNode.AddObserver( vtk.vtkCommand.ModifiedEvent, partial( self.ComputeCalibration, usCalibrationNode ) )
  
  
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
        
     
  def SelectMarkedPoint( self, usCalibrationNode ):
    if ( usCalibrationNode is None ):
      return 
     
    markedPointsList = usCalibrationNode.GetNodeReference( ImagelessUSCalibrationWidget.MARKED_POINTS_ROLE )
    if ( markedPointsList is None ):
      return
    
    if ( markedPointsList.GetNumberOfFiducials() >= 2 ):
      logging.warning( "Newly selected points not used. Points list already contains previously selected points." )
      
    frwLogic = slicer.modules.fiducialregistrationwizard.logic()
    if ( frwLogic is None ):
      return
      
    frwLogic.AddFiducial( usCalibrationNode.GetNodeReference( ImagelessUSCalibrationWidget.STYLUSTIP_TO_PROBE_TRANSFORM_ROLE ), markedPointsList )
      
      
  def ResetMarkedPoints( self, usCalibrationNode ):
    if ( usCalibrationNode is None ):
      return
      
    markedPointsList = usCalibrationNode.GetNodeReference( ImagelessUSCalibrationWidget.MARKED_POINTS_ROLE )
    if ( markedPointsList is None ):
      return
     
    markedPointsList.RemoveAllMarkups()
    

  def SelectUnmarkedPoint( self, usCalibrationNode ):
    if ( usCalibrationNode is None ):
      return 
     
    unmarkedPointsList = usCalibrationNode.GetNodeReference( ImagelessUSCalibrationWidget.UNMARKED_POINTS_ROLE )
    if ( unmarkedPointsList is None ):
      return
    
    if ( unmarkedPointsList.GetNumberOfFiducials() >= 2 ):
      logging.warning( "Newly selected points not used. Points list already contains previously selected points." )
      
    frwLogic = slicer.modules.fiducialregistrationwizard.logic()
    if ( frwLogic is None ):
      return
      
    frwLogic.AddFiducial( usCalibrationNode.GetNodeReference( ImagelessUSCalibrationWidget.STYLUSTIP_TO_PROBE_TRANSFORM_ROLE ), unmarkedPointsList )
      
      
  def ResetUnmarkedPoints( self, usCalibrationNode ):
    if ( usCalibrationNode is None ):
      return
      
    unmarkedPointsList = usCalibrationNode.GetNodeReference( ImagelessUSCalibrationWidget.UNMARKED_POINTS_ROLE )
    if ( unmarkedPointsList is None ):
      return
     
    unmarkedPointsList.RemoveAllMarkups()
    
    
  def SetStylusTipToProbeTransform( self, stylusTipToProbeNode, usCalibrationNode ):
    if ( usCalibrationNode is None or stylusTipToProbeNode is None ):
      return 
     
    usCalibrationNode.SetAndObserveNodeReferenceID( ImagelessUSCalibrationWidget.STYLUSTIP_TO_PROBE_TRANSFORM_ROLE, stylusTipToProbeNode.GetID() )
    
    
  def SetImageToProbeTransform( self, imageToProbeNode, usCalibrationNode ):
    if ( usCalibrationNode is None or imageToProbeNode is None ):
      return 
     
    usCalibrationNode.SetAndObserveNodeReferenceID( ImagelessUSCalibrationWidget.IMAGE_TO_PROBE_TRANSFORM_ROLE, imageToProbeNode.GetID() )
    
    
  def SetDepth( self, depth, usCalibrationNode ):
    if ( usCalibrationNode is None ):
      return 
     
    usCalibrationNode.SetAttribute( ImagelessUSCalibrationWidget.DEPTH_ROLE, str( depth ) )
      
      
  def GetFirstNodeByClassByPrefix( self, className, prefixes ):
    nodeCollection = slicer.mrmlScene.GetNodesByClass( className )
    
    for i in range( nodeCollection.GetNumberOfItems() ):
      currNode = nodeCollection.GetItemAsObject( i )
      for prefix in prefixes:
        if prefix in currNode.GetName():
          return currNode
        
    return None
    
    
  def ApplyTransformToImage( self, usCalibrationNode ):
    if ( usCalibrationNode is None ):
      return
            
    imageToProbeTransformNode = usCalibrationNode.GetNodeReference( ImagelessUSCalibrationWidget.IMAGE_TO_PROBE_TRANSFORM_ROLE )
    usImageNode = usCalibrationNode.GetNodeReference( ImagelessUSCalibrationWidget.ULTRASOUND_IMAGE_ROLE )
    if ( imageToProbeTransformNode is None or usImageNode is None ):
      return
      
    # Toggle whether the image is under the image to probe transform
    if ( usImageNode.GetTransformNodeID() == imageToProbeTransformNode.GetID() ):
      usImageNode.SetAndObserveTransformNodeID( "" )
    else:
      usImageNode.SetAndObserveTransformNodeID( imageToProbeTransformNode.GetID() )
    
    
  def ComputeCalibration( self, usCalibrationNode, listNode, eventid ): #Ignore listnode and eventid
    if ( usCalibrationNode is None ):
      return
      
    markedPointsList = usCalibrationNode.GetNodeReference( ImagelessUSCalibrationWidget.MARKED_POINTS_ROLE )
    unmarkedPointsList = usCalibrationNode.GetNodeReference( ImagelessUSCalibrationWidget.UNMARKED_POINTS_ROLE )
    if ( markedPointsList is None or unmarkedPointsList is None ):
      return
      
    if ( markedPointsList.GetNumberOfFiducials() < 2 ):
      usCalibrationNode.SetAttribute( ImagelessUSCalibrationWidget.OUTPUT_MESSAGE_ROLE, "Insufficient number of marked corner points selected." )
      return
      
    if ( unmarkedPointsList.GetNumberOfFiducials() < 2 ):
      usCalibrationNode.SetAttribute( ImagelessUSCalibrationWidget.OUTPUT_MESSAGE_ROLE, "Insufficient number of unmarked corner points selected." )
      return
      
    # Assume the ordering of points is:
    # Unmarked near, marked near, unmarked far, marked far
      
    # Find the points in the probe coordinate system
    markedCorner1 = [ 0, 0, 0 ]
    markedPointsList.GetNthFiducialPosition( 0, markedCorner1 )
    markedCorner2 = [ 0, 0, 0 ]
    markedPointsList.GetNthFiducialPosition( 1, markedCorner2 )
    
    unmarkedCorner1 = [ 0, 0, 0 ]
    unmarkedPointsList.GetNthFiducialPosition( 0, unmarkedCorner1 )
    unmarkedCorner2 = [ 0, 0, 0 ]
    unmarkedPointsList.GetNthFiducialPosition( 1, unmarkedCorner2 )
    
    # Find the near points
    markedNearPoint = [ 0, 0, 0 ]
    vtk.vtkMath.Add( markedCorner1, markedCorner2, markedNearPoint )
    vtk.vtkMath.MultiplyScalar( markedNearPoint, 0.5 )
    
    unmarkedNearPoint = [ 0, 0, 0 ]
    vtk.vtkMath.Add( unmarkedCorner1, unmarkedCorner2, unmarkedNearPoint )
    vtk.vtkMath.MultiplyScalar( unmarkedNearPoint, 0.5 )
    
    # Find the vector required for computing the far points
    markedUnmarkedVector = [ 0, 0, 0 ]
    vtk.vtkMath.Subtract( unmarkedNearPoint, markedNearPoint, markedUnmarkedVector )
    
    markedCornerVector = [ 0, 0, 0 ]
    vtk.vtkMath.Subtract( markedCorner2, markedCorner1, markedCornerVector )
    
    unmarkedCornerVector = [ 0, 0, 0 ]
    vtk.vtkMath.Subtract( unmarkedCorner2, unmarkedCorner1, unmarkedCornerVector )
    
    markedFarVector = [ 0, 0, 0 ]
    vtk.vtkMath.Cross( markedUnmarkedVector, markedCornerVector, markedFarVector )
    vtk.vtkMath.Normalize( markedFarVector )
    
    unmarkedFarVector = [ 0, 0, 0 ]
    vtk.vtkMath.Cross( markedUnmarkedVector, unmarkedCornerVector, unmarkedFarVector )
    vtk.vtkMath.Normalize( unmarkedFarVector )
    
    # Compute the far points
    try:
      depth = float( usCalibrationNode.GetAttribute( ImagelessUSCalibrationWidget.DEPTH_ROLE ) )
    except TypeError:
      usCalibrationNode.SetAttribute( ImagelessUSCalibrationWidget.OUTPUT_MESSAGE_ROLE, "Depth improperly specified." )
      return
    
    vtk.vtkMath.MultiplyScalar( markedFarVector, depth )
    markedFarPoint = [ 0, 0, 0 ]
    vtk.vtkMath.Add( markedNearPoint, markedFarVector, markedFarPoint )
    
    vtk.vtkMath.MultiplyScalar( unmarkedFarVector, depth )
    unmarkedFarPoint = [ 0, 0, 0 ]
    vtk.vtkMath.Add( unmarkedNearPoint, unmarkedFarVector, unmarkedFarPoint )
    
    # Now, we can assemble the probe points
    probePoints = vtk.vtkPoints()
    probePoints.InsertNextPoint( unmarkedNearPoint )
    probePoints.InsertNextPoint( markedNearPoint )
    probePoints.InsertNextPoint( unmarkedFarPoint )
    probePoints.InsertNextPoint( markedFarPoint )
    
    # Compute the scaling factor
    usImageNode = usCalibrationNode.GetNodeReference( ImagelessUSCalibrationWidget.ULTRASOUND_IMAGE_ROLE )
    if ( usImageNode is None or usImageNode.GetImageData() is None ):
      usCalibrationNode.SetAttribute( ImagelessUSCalibrationWidget.OUTPUT_MESSAGE_ROLE, "No ultrasound image is selected." ) 
      return
      
    # The scale is the ratio of depth to y pixels
    usImageDimensions = [ 0, 0, 0 ]
    usImageNode.GetImageData().GetDimensions( usImageDimensions )
    
    pixelsToMmScale = depth / usImageDimensions[ 1 ] # y dimension
    
    imagePixelToImageMm = vtk.vtkTransform()
    imagePixelToImageMm.Scale( [ pixelsToMmScale, pixelsToMmScale, pixelsToMmScale ] ) # Uniform scaling - similarity transform
    print pixelsToMmScale
    
    # Next, we can assembla the image points
    imagePoints_ImageMm = vtk.vtkPoints()
    imagePoints_ImageMm.InsertNextPoint( [ 0, 0, 0 ] )
    imagePoints_ImageMm.InsertNextPoint( [ usImageDimensions[ 0 ] * pixelsToMmScale, 0, 0 ] )
    imagePoints_ImageMm.InsertNextPoint( [ 0, depth, 0 ] )
    imagePoints_ImageMm.InsertNextPoint( [ usImageDimensions[ 0 ] * pixelsToMmScale, depth, 0 ] )
    
    # Compute the transform (without the scaling)
    imageToProbeTransformNode = usCalibrationNode.GetNodeReference( ImagelessUSCalibrationWidget.IMAGE_TO_PROBE_TRANSFORM_ROLE )
    if ( imageToProbeTransformNode is None ):
      usCalibrationNode.SetAttribute( ImagelessUSCalibrationWidget.OUTPUT_MESSAGE_ROLE, "No output ImageToProbe transform specified." )
      return
    
    imageMmToProbe = vtk.vtkLandmarkTransform()
    imageMmToProbe.SetSourceLandmarks( imagePoints_ImageMm )
    imageMmToProbe.SetTargetLandmarks( probePoints )
    imageMmToProbe.SetModeToRigidBody()
    imageMmToProbe.Update()

    # The overall ImageToProbe = ImageMmToProbe * ImagePixelToImageMm
    imageToProbeTransform = vtk.vtkTransform()
    imageToProbeTransform.PreMultiply()
    imageToProbeTransform.Concatenate( imageMmToProbe )
    imageToProbeTransform.Concatenate( imagePixelToImageMm )
    
    imageToProbeMatrix = vtk.vtkMatrix4x4()
    imageToProbeTransform.GetMatrix( imageToProbeMatrix )
    
    imageToProbeTransformNode.SetMatrixTransformToParent( imageToProbeMatrix )
    
    usCalibrationNode.SetAttribute( ImagelessUSCalibrationWidget.OUTPUT_MESSAGE_ROLE, "Success!" )
    # Note that we cannot compute RMS error, because we expect the error to be non-zero 
    
      



class ImagelessUSCalibrationTest(ScriptedLoadableModuleTest):
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
    self.test_ImagelessUSCalibration1()

  def test_ImagelessUSCalibration1(self):
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
    logic = ImagelessUSCalibrationLogic()
    self.assertIsNotNone( logic.hasImageData(volumeNode) )
    self.delayDisplay('Test passed!')
