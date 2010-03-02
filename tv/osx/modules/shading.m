/*
# Miro - an RSS based video player application
# Copyright (C) 2005-2010 Participatory Culture Foundation
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA
#
# In addition, as a special exception, the copyright holders give
# permission to link the code of portions of this program with the OpenSSL
# library.
#
# You must obey the GNU General Public License in all respects for all of
# the code used other than OpenSSL. If you modify file(s) with this
# exception, you may extend this exception to your version of the file(s),
# but you are not obligated to do so. If you do not wish to do so, delete
# this exception statement from your version. If you delete this exception
# statement from all source files in the program, then also delete it here.
*/

#include <ApplicationServices/ApplicationServices.h>
#include <Cocoa/Cocoa.h>
#include <Python.h>

typedef struct _interpolator_info
{
    float   start_red, start_green, start_blue;
    float   diff_red, diff_green, diff_blue;
} interpolator_info;

static void linear_interpolator(void* raw_info, const float* in, float* out)
{
    interpolator_info* info = (interpolator_info*)raw_info;

    out[0] = info->start_red   + (info->diff_red   * in[0]);
    out[1] = info->start_green + (info->diff_green * in[0]);
    out[2] = info->start_blue  + (info->diff_blue  * in[0]);
    
    //printf("---------------------------------------------------------\n");
    //printf("start: (%f, %f, %f)\n", info->start_red, info->start_green, info->start_blue);
    //printf("end:   (%f, %f, %f)\n", info->end_red, info->end_green, info->end_blue);
    //printf("in:    %f\n", in[0]);
    //printf("out:   (%f, %f, %f)\n", out[0], out[1], out[2]);
}

static const float               input_value_range[2]    = { 0, 1 };
static const float               output_value_ranges [6] = { 0, 1, 0, 1, 0, 1 };
static const CGFunctionCallbacks callbacks = { 0, &linear_interpolator, NULL };

static PyObject* shading_draw_axial(PyObject* self, PyObject* args)
{
    PyObject* gradient = NULL;
    PyArg_ParseTuple(args, "O", &gradient);

    PyObject* start_color = PyObject_GetAttrString(gradient, "start_color");
    PyObject* end_color = PyObject_GetAttrString(gradient, "end_color");
    PyObject* start_color_seq = PySequence_Fast(start_color, "start_color is not a sequence");
    PyObject* end_color_seq = PySequence_Fast(end_color, "end_color is not a sequence");

    interpolator_info info;
    info.start_red   = PyFloat_AsDouble(PySequence_Fast_GET_ITEM(start_color_seq, 0));
    info.start_green = PyFloat_AsDouble(PySequence_Fast_GET_ITEM(start_color_seq, 1));
    info.start_blue  = PyFloat_AsDouble(PySequence_Fast_GET_ITEM(start_color_seq, 2));
    info.diff_red    = PyFloat_AsDouble(PySequence_Fast_GET_ITEM(end_color_seq, 0)) - info.start_red;
    info.diff_green  = PyFloat_AsDouble(PySequence_Fast_GET_ITEM(end_color_seq, 1)) - info.start_green;
    info.diff_blue   = PyFloat_AsDouble(PySequence_Fast_GET_ITEM(end_color_seq, 2)) - info.start_blue;

    CGFunctionRef shading_function = CGFunctionCreate(&info,
                                                      1,
                                                      input_value_range,
                                                      3,
                                                      output_value_ranges,
                                                      &callbacks);

    PyObject* x1_obj = PyObject_GetAttrString(gradient, "x1");
    PyObject* y1_obj = PyObject_GetAttrString(gradient, "y1");
    PyObject* x2_obj = PyObject_GetAttrString(gradient, "x2");
    PyObject* y2_obj = PyObject_GetAttrString(gradient, "y2");

    float x1 = PyFloat_AsDouble(x1_obj);
    float y1 = PyFloat_AsDouble(y1_obj);
    float x2 = PyFloat_AsDouble(x2_obj);
    float y2 = PyFloat_AsDouble(y2_obj);

    CGColorSpaceRef colorspace = CGColorSpaceCreateDeviceRGB();
    CGShadingRef shading = CGShadingCreateAxial(colorspace,
                                                CGPointMake(x1, y1),
                                                CGPointMake(x2, y2),
                                                shading_function,
                                                false,
                                                false);

    CGContextRef context = [[NSGraphicsContext currentContext] graphicsPort];
    CGContextDrawShading(context, shading);
    
    CGShadingRelease(shading);
    CGColorSpaceRelease(colorspace);
    CGFunctionRelease(shading_function);

    Py_DECREF(start_color);
    Py_DECREF(end_color);
    Py_DECREF(start_color_seq);
    Py_DECREF(end_color_seq);
    Py_DECREF(x1_obj);
    Py_DECREF(y1_obj);
    Py_DECREF(x2_obj);
    Py_DECREF(y2_obj);

    Py_INCREF(Py_None);

    return Py_None;
}

static PyMethodDef ShadingMethods[] = 
{
    { "draw_axial", shading_draw_axial, METH_VARARGS, 
      "Draw an axial gradient in the current context using CoreGraphics' CGShading" },
    { NULL, NULL, 0, NULL }
};

PyMODINIT_FUNC initshading(void)
{
    Py_InitModule("shading", ShadingMethods);
}
