(function () {
    const WU = window.SkySceneWidgetUtils;

    window.SkySceneWidgetLayer = function () {
        this.magScaleWidget = new window.SkySceneMagScaleWidget();
        this.numericMapScaleWidget = new window.SkySceneNumericMapScaleWidget();
        this.telradWidget = new window.SkySceneTelradWidget();
        this.eyepieceWidget = new window.SkySceneEyepieceWidget();
        this.pickerWidget = new window.SkyScenePickerWidget();
        this.panelGap = 8;
    };

    window.SkySceneWidgetLayer.prototype._leftBottomPanels = function (sceneCtx) {
        const style = sceneCtx.widgetPanelStyle;
        if (!style) return { mag: { x: 0, y: 0, w: 0, h: 0 }, numeric: { x: 0, y: 0, w: 0, h: 0 } };
        const magSize = this.magScaleWidget.measure(sceneCtx) || { w: 0, h: 0 };
        const numericSize = this.numericMapScaleWidget.measure(sceneCtx) || { w: 0, h: 0 };
        const y = (sceneCtx.height || 0) - (style.margin || 0) - Math.max(magSize.h || 0, numericSize.h || 0);
        const x1 = style.margin || 0;
        const x2 = x1 + (magSize.w || 0) + this.panelGap;

        return {
            mag: { x: x1, y: y, w: magSize.w || 0, h: magSize.h || 0 },
            numeric: { x: x2, y: y, w: numericSize.w || 0, h: numericSize.h || 0 },
        };
    };

    window.SkySceneWidgetLayer.prototype.draw = function (sceneCtx) {
        if (!sceneCtx || !sceneCtx.frontCtx || !sceneCtx.meta) return;
        const widgets = sceneCtx.meta.widgets || null;
        if (!widgets) return;

        sceneCtx.widgetPanelStyle = WU.panelStyle(sceneCtx);

        if (widgets.show_telrad) {
            this.telradWidget.draw(sceneCtx);
        }
        if (widgets.show_eyepiece) {
            this.eyepieceWidget.draw(sceneCtx);
        }
        if (widgets.show_picker) {
            this.pickerWidget.draw(sceneCtx);
        }

        const rects = this._leftBottomPanels(sceneCtx);
        if (widgets.show_mag_scale) {
            this.magScaleWidget.draw(sceneCtx, rects.mag);
        }
        if (widgets.show_numeric_fov) {
            this.numericMapScaleWidget.draw(sceneCtx, rects.numeric);
        }
    };
})();
