/**
 * reflection.js v0.2
 *
 * Script by Cow http://cow.neondragon.net
 *           Gfx http://www.jroller.com/page/gfx/
 *           Sitharus http://www.sitharus.com
 *
 * Freely distributable under MIT-style license.
 */

function addReflections() {
	var reflect = document.getElementsByClassName('reflect');
	for (i=0;i<reflect.length;i++) {
		try {
			var canvas = document.createElement('canvas');
			var context = canvas.getContext("2d");
			
			if (Element.hasClassName(reflect[i], "wholeimage")) {
				var canvasHeight = reflect[i].height;
				var divHeight = reflect[i].height*2;
			} else {
				var canvasHeight = reflect[i].height/2;
				var divHeight = reflect[i].height*1.5;
			}
			
			var canvasWidth = reflect[i].width;
			p = reflect[i];
			canvas.style.height = canvasHeight+'px';
			canvas.style.width = canvasWidth+'px';
			canvas.height = canvasHeight;
			canvas.width = canvasWidth;
			
			var d = document.createElement('div');
			d.style.width = canvasWidth+'px';
			d.style.height = divHeight+'px';
			p.parentNode.replaceChild(d, reflect[i]);
			
			d.appendChild(p);
			d.appendChild(document.createElement('br'));
			d.appendChild(canvas);
			
			context.save();
			
			context.translate(0,canvasHeight*2-1);
			context.scale(1,-1);
			
			context.drawImage(reflect[i], 0, reflect[i].height-canvasHeight, canvasWidth, canvasHeight, 0, canvasHeight, canvasWidth, canvasHeight);
			
			context.globalCompositeOperation = "destination-out";
			
			var gradient = context.createLinearGradient(0, canvasHeight, 0, canvasWidth);
			gradient.addColorStop(0, "rgba(255, 255, 255, 1.0)");
			
			if (Element.hasClassName(reflect[i], "wholeimage")) {
				gradient.addColorStop(0.5, "rgba(255, 255, 255, 0.3)");
			} else {
				gradient.addColorStop(0.9, "rgba(255, 255, 255, 0.3)");
			}

			context.fillStyle = gradient;
			if (navigator.appVersion.indexOf('WebKit') != -1) {
				context.fill();
			} else {
				context.fillRect(0, 0, canvasWidth, canvasHeight*2);
			}

			context.restore();
		} catch (e) {
	    }
	}
}

Event.observe(window, 'load', addReflections, false);