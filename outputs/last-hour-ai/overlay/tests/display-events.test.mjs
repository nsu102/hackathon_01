import test from 'node:test';import assert from 'node:assert/strict';
import {invalidatesCalibration} from '../display-events.cjs';
test('Dock/work-area updates do not reset gaze; selected-monitor geometry changes do',()=>{
 const selected={id:4};
 assert.equal(invalidatesCalibration({id:4},['workArea'],selected),false);
 for(const field of ['bounds','scaleFactor','rotation'])assert.equal(invalidatesCalibration({id:4},[field],selected),true);
 assert.equal(invalidatesCalibration({id:9},['bounds'],selected),false);
 assert.equal(invalidatesCalibration({id:4},['bounds'],null),false);
});
