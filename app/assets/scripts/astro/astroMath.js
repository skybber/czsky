//=================================
//            AstroMath
//=================================

// Class AstroMath having 'static' methods
function AstroMath() {}

// Constant for conversion Degrees => Radians (rad = deg*AstroMath.D2R)
AstroMath.D2R = Math.PI/180.0;
// Constant for conversion Radians => Degrees (deg = rad*AstroMath.R2D)
AstroMath.R2D = 180.0/Math.PI;
/**
 * Function sign
 * @param x value for checking the sign
 * @return -1, 0, +1 respectively if x < 0, = 0, > 0
 */
AstroMath.sign = function(x) { return x > 0 ? 1 : (x < 0 ? -1 : 0 ); };

/**
 * Function cosd(degrees)
 * @param x angle in degrees
 * @returns the cosine of the angle
 */
AstroMath.cosd = function(x) {
	if (x % 90 == 0) {
		var i = Math.abs(Math.floor(x / 90 + 0.5)) % 4;
		switch (i) {
			case 0:	return 1;
			case 1:	return 0;
			case 2:	return -1;
			case 3:	return 0;
		}
	}
	return Math.cos(x*AstroMath.D2R);
};

/**
 * Function sind(degrees)
 * @param x angle in degrees
 * @returns the sine of the angle
 */
AstroMath.sind = function(x) {
	if (x % 90 === 0) {
		var i = Math.abs(Math.floor(x / 90 - 0.5)) % 4;
		switch (i) {
			case 0:	return 1;
			case 1:	return 0;
			case 2:	return -1;
			case 3:	return 0;
		}
	}

	return Math.sin(x*AstroMath.D2R);
};

/**
 * Function tand(degrees)
 * @param x angle in degrees
 * @returns the tangent of the angle
 */
AstroMath.tand = function(x) {
	var resid;

	resid = x % 360;
	if (resid == 0 || Math.abs(resid) == 180) {
		return 0;
	} else if (resid == 45 || resid == 225) {
		return 1;
	} else if (resid == -135 || resid == -315) {
		return -1
	}

	return Math.tan(x * AstroMath.D2R);
};

/**
 * Function asin(degrees)
 * @param sine value [0,1]
 * @return the angle in degrees
 */
AstroMath.asind = function(x) { return Math.asin(x)*AstroMath.R2D; };

/**
 * Function acos(degrees)
 * @param cosine value [0,1]
 * @return the angle in degrees
 */
AstroMath.acosd = function(x) { return Math.acos(x)*AstroMath.R2D; };

/**
 * Function atan(degrees)
 * @param tangent value
 * @return the angle in degrees
 */
AstroMath.atand = function(x) { return Math.atan(x)*AstroMath.R2D; };

/**
 * Function atan2(y,x)
 * @param y y component of the vector
 * @param x x component of the vector
 * @return the angle in radians
 */
AstroMath.atan2 = function(y,x) {
	if (y != 0.0) {
		var sgny = AstroMath.sign(y);
		if (x != 0.0) {
			var phi = Math.atan(Math.abs(y/x));
			if (x > 0.0) return phi*sgny;
			else if (x < 0) return (Math.PI-phi)*sgny;
		} else return (Math.PI/2)*sgny;
	} else {
		return x > 0.0 ? 0.0 : (x < 0 ? Math.PI : 0.0/0.0);
	}
}  

/**
 * Function atan2d(y,x)
 * @param y y component of the vector
 * @param x x component of the vector
 * @return the angle in degrees
 */
AstroMath.atan2d = function(y,x) {
	return AstroMath.atan2(y,x)*AstroMath.R2D;
}

/*=========================================================================*/
/**
 * Computation of hyperbolic cosine
 * @param x argument
 */
AstroMath.cosh = function(x) {
	return (Math.exp(x)+Math.exp(-x))/2;
}

/**
 * Computation of hyperbolic sine
 * @param x argument
 */
AstroMath.sinh = function(x) {
	return (Math.exp(x)-Math.exp(-x))/2;
}

/**
 * Computation of hyperbolic tangent
 * @param x argument
 */
AstroMath.tanh = function(x) {
	return (Math.exp(x)-Math.exp(-x))/(Math.exp(x)+Math.exp(-x));
}

/**
 * Computation of Arg cosh
 * @param x argument in degrees. Must be in the range [ 1, +infinity ]
 */
AstroMath.acosh = function(x) {
	return(Math.log(x+Math.sqrt(x*x-1.0)));
}

/**
 * Computation of Arg sinh
 * @param x argument in degrees
 */
AstroMath.asinh = function(x) {
	return(Math.log(x+Math.sqrt(x*x+1.0)));
}

/**
 * Computation of Arg tanh
 * @param x argument in degrees. Must be in the range ] -1, +1 [
 */
AstroMath.atanh = function(x) {
	return(0.5*Math.log((1.0+x)/(1.0-x)));
}

//=============================================================================
//      Special Functions using trigonometry
//=============================================================================
/**
 * Computation of sin(x)/x
 *	@param x in degrees.
 * For small arguments x <= 0.001, use approximation 
 */
AstroMath.sinc = function(x) {
	var ax = Math.abs(x);
	var y;

	if (ax <= 0.001) {
		ax *= ax;
		y = 1 - ax*(1.0-ax/20.0)/6.0;
	} else {
		y = Math.sin(ax)/ax;
	}

	return y;
}

/**
 * Computes asin(x)/x
 * @param x in degrees.
 * For small arguments x <= 0.001, use an approximation
 */
AstroMath.asinc = function(x) {
	var ax = Math.abs(x);
	var y;

	if (ax <= 0.001) {
		ax *= ax; 
		y = 1 + ax*(6.0 + ax*(9.0/20.0))/6.0;
	} else {
		y = Math.asin(ax)/ax;	// ???? radians ???
	}

	return (y);
}


//=============================================================================
/**
 * Computes the hypotenuse of x and y
 * @param x value
 * @param y value
 * @return sqrt(x*x+y*y)
 */
AstroMath.hypot = function(x,y) {
	return Math.sqrt(x*x+y*y);
}

/** Generate the rotation matrix from the Euler angles
 * @param z	Euler angle
 * @param theta	Euler angle
 * @param zeta	Euler angles
 * @return R [3][3]		the rotation matrix
 * The rotation matrix is defined by:<pre>
 *    R =      R_z(-z)      *        R_y(theta)     *     R_z(-zeta)
 *   |cos.z -sin.z  0|   |cos.the  0 -sin.the|   |cos.zet -sin.zet 0|
 * = |sin.z  cos.z  0| x |   0     1     0   | x |sin.zet  cos.zet 0|
 *   |   0      0   1|   |sin.the  0  cos.the|   |   0        0    1|
 * </pre>
 */
AstroMath.eulerMatrix = function(z, theta, zeta) {
	var R = new Array(3);
	R[0] = new Array(3);
	R[1] = new Array(3);
	R[2] = new Array(3);
	var cosdZ = AstroMath.cosd(z);
	var sindZ = AstroMath.sind(z);
	var cosdTheta = AstroMath.cosd(theta);
	var w = AstroMath.sind(theta) ;
	var cosdZeta = AstroMath.cosd(zeta);
	var sindZeta = AstroMath.sind(zeta);

	R[0][0] = cosdZeta*cosdTheta*cosdZ - sindZeta*sindZ;
	R[0][1] = -sindZeta*cosdTheta*cosdZ - cosdZeta*sindZ;
	R[0][2] = -w*cosdZ;

	R[1][0] = cosdZeta*cosdTheta*sindZ + sindZeta*cosdZ;
	R[1][1] = -sindZeta*cosdTheta*sindZ + cosdZeta*cosdZ;
	R[1][2] = -w*sindZ;

	R[2][0] = -w*cosdZeta;
	R[2][1] = -w*cosdZ;
	R[2][2] = cosdTheta;
	return R ;
};


AstroMath.displayMatrix = function(m) {
	// Number of rows
	var nbrows = m.length;
	// Max column count
	var nbcols = 0
	for (var i=0; i<nbrows; i++) {
		if (m[i].length > nbcols) nbcols = m[i].length;
	}
	var str = '<table>\n';
	for (var i=0; i<nbrows; i++) {
		str += '<tr>';
		for (var j=0; j<nbrows; j++) {
			str += '<td>';
			if (i < m[i].length)
				str += (m[i][j]).toString();
			str += '</td>';
		}
		str += '</td>\n';
	}
	str += '</table>\n';

	return str;
}

/**
 * Calculates the Local Sidereal Time (LST) for a given longitude and Greenwich Sidereal Time (GST).
 *
 * Local Sidereal Time is used in astronomy to determine locations in the sky specific to a geographic location.
 *
 * @function
 * @param {number} date - date
 * @param {number} lon - The geographic longitude in degrees where the calculation is performed.
 * @returns {number} The Local Sidereal Time in degrees, normalized to a value between 0 and 360.
 */
AstroMath.localSiderealTime = function (date, lon) {
    const year = date.getUTCFullYear();
    const month = date.getUTCMonth() + 1; // JavaScript months are 0-11.
    const day = date.getUTCDate();
    const hours = date.getUTCHours();
    const minutes = date.getUTCMinutes();
    const seconds = date.getUTCSeconds();

    const jd =
        367 * year -
        Math.floor((7 * (year + Math.floor((month + 9) / 12))) / 4) +
        Math.floor((275 * month) / 9) +
        day +
        1721013.5 +
        (hours + minutes / 60 + seconds / 3600) / 24 -
        0.5 * Math.sign(100 * year + month - 190002.5) +
        0.5;

    const t = (jd - 2451545.0) / 36525;

    let gmst =
        280.46061837 +
        360.98564736629 * (jd - 2451545) +
        0.000387933 * t ** 2 -
        (t ** 3) / 38710000;

    gmst = ((gmst % 360) + 360) % 360;

    const gmstRadians = gmst * (Math.PI / 180);;

    const lst = (gmstRadians + lon) % (2 * Math.PI);

    return lst >= 0 ? lst : lst + 2 * Math.PI;
}

/**
 * Converts equatorial coordinates (right ascension and declination) to horizontal coordinates (azimuth and altitude).
 *
 * The conversion is based on the observer's geographic latitude and local sidereal time.
 *
 * @method equatorialToHorizontal
 * @memberof AstroMath
 * @param {number} lst
 * @param {number} lat
 * @param {number} ra - The right ascension in hours.
 * @param {number} dec*/
AstroMath.equatorialToHorizontal = function(lst, lat, ra, dec) {
	let hourAngle = (lst - ra);
	if (hourAngle < 0) {
		hourAngle += 2 * Math.PI;
	}

	const sinLat = Math.sin(lat);
	const cosLat = Math.cos(lat);
	const sinDec = Math.sin(dec);
	const cosDec = Math.cos(dec);
	const sinHA = Math.sin(hourAngle);
	const cosHA = Math.cos(hourAngle);

	const sinAlt = sinDec * sinLat + cosDec * cosLat * cosHA;
	let alt = Math.asin(sinAlt);

	let cosAlt = Math.sqrt(Math.max(0.0, 1.0 - sinAlt * sinAlt));
	if (Math.abs(cosAlt) < 1e-15) {
		cosAlt = Math.cos(alt);
	}

	let arg = (sinDec - sinLat * sinAlt) / (cosLat * cosAlt);
	let az = 0.0;

	if (arg <= -1.0) {
		az = Math.PI;
	} else if (arg >= 1.0) {
		az = 0.0;
	} else {
		az = Math.acos(arg);
	}

	if (sinHA > 0.0 && Math.abs(az) > 1e-15) {
		az = 2.0 * Math.PI - az;
	}

	az = (2 * Math.PI - az) % (2 * Math.PI);

	if (az < 0) {
		az += 2 * Math.PI;
	}

	return { az, alt };
}

/**
 * Converts horizontal coordinates (altitude and azimuth) to equatorial coordinates
 * (right ascension and declination).
 *
 * @param {number} lst - The local sidereal time in radians.
 * @param {number} lat - The observer's geographical latitude in radians.
 * @param {number} az - The azimuth angle of the object in radians.
 * @param {number} alt - The altitude angle of the object in radians.
 * @return {Object} An object containing the right ascension (`ra`) and declination (`dec`) in radians.
 */
AstroMath.horizontalToEquatorial = function(lst, lat, az, alt) {
	const sinLat = Math.sin(lat);
	const cosLat = Math.cos(lat);

	const sinAlt = Math.sin(alt);
	const cosAlt = Math.cos(alt);

	let sinDec = sinLat * sinAlt + cosLat * cosAlt * Math.cos(az);

	if (sinDec > 1.0) {
		sinDec = 1.0;
	} else if (sinDec < -1.0) {
		sinDec = -1.0;
	}

	const dec = Math.asin(sinDec);
	const cosDec = Math.cos(dec);

	const denom = cosDec * cosLat;
	let hourAngle = 0.0;

	if (Math.abs(denom) < 1.0e-15) {
		hourAngle = 0.0;
	} else {
		let cosHA = (sinAlt - sinDec * sinLat) / denom;
		if (cosHA > 1.0) {
			cosHA = 1.0;
		} else if (cosHA < -1.0) {
			cosHA = -1.0;
		}

		let sinHA = Math.sqrt(Math.max(0.0, 1.0 - cosHA * cosHA));
		if (az >= Math.PI) {
		  sinHA = -sinHA;
		}
		hourAngle = Math.atan2(sinHA, cosHA);
	}

	let ra = (lst - hourAngle) % (2.0 * Math.PI);
	if (ra < 0) {
		ra += 2.0 * Math.PI;
	}

	return { ra, dec };
}
