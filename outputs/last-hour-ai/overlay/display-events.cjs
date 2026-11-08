// Work-area changes (Dock/menu chrome) do not change monitor DIP coordinates.
function invalidatesCalibration(display, changedMetrics, selected){
 if(!selected||String(display.id)!==String(selected.id))return false;
 return changedMetrics.some(metric=>['bounds','scaleFactor','rotation'].includes(metric));
}
module.exports={invalidatesCalibration};
