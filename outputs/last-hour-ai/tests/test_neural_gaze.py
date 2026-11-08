import unittest
import importlib.util
from last_hour.neural_gaze import validate_request, FACE_POINTS

class NeuralInputTests(unittest.TestCase):
    def test_only_bounded_transient_camera_fields_are_accepted(self):
        value={'image':'a'*40,'points':[[100.,100.]]*6,'bbox':[10,20,300,400]}
        self.assertEqual(validate_request(value),value)
        for changes in [{'image':'x'*2000001},{'points':[[float('nan'),0]]*6},{'points':[[0,0]]*5},{'bbox':[0,0,1,2,3]},{'save_image':True}]:
            with self.assertRaises(ValueError):validate_request({**value,**changes})

@unittest.skipUnless(importlib.util.find_spec('cv2'), 'optional neural inference environment')
class NormalizationTests(unittest.TestCase):
    def test_known_camera_geometry_projects_eye_nose_template_into_centered_patch(self):
        import cv2,numpy as np
        from last_hour.neural_gaze import normalize_face
        template=np.array(FACE_POINTS,dtype=np.float64)
        camera=np.array([[2560.,0,320],[0,2560.,240],[0,0,1.]])
        points,_=cv2.projectPoints(template,np.zeros(3),np.array([0.,0.,700.]),camera,np.zeros(5))
        image=np.zeros((480,640,3),dtype=np.uint8)
        # Full-frame crop gives exactly the above dummy intrinsic matrix.
        patch,rotation,head,residual=normalize_face(image,points.reshape(6,2),[0,0,640,480])
        self.assertEqual(patch.shape,(224,224,3));self.assertTrue(np.isfinite(rotation).all());self.assertLess(residual,.01)
        self.assertGreater(np.linalg.det(rotation),.99)
    def test_invalid_region_fails_without_inference(self):
        import numpy as np
        from last_hour.neural_gaze import normalize_face
        image=np.zeros((480,640,3),dtype=np.uint8)
        with self.assertRaises(ValueError):normalize_face(image,[[0.,0.]]*6,[-1,0,100,100])
