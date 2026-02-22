(function () {
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
        const magSize = this.magScaleWidget.measure(sceneCtx);
        const numericSize = this.numericMapScaleWidget.measure(sceneCtx);
        const y = sceneCtx.height - style.margin - Math.max(magSize.h, numericSize.h);
        const x1 = style.margin;
        const x2 = x1 + magSize.w + this.panelGap;

        return {
            mag: { x: x1, y: y, w: magSize.w, h: magSize.h },
            numeric: { x: x2, y: y, w: numericSize.w, h: numericSize.h },
        };
    };

    window.SkySceneWidgetLayer.prototype.draw = function (sceneCtx) {
        if (!sceneCtx || !sceneCtx.overlayCtx || !sceneCtx.meta) return;
        const widgets = sceneCtx.meta.widgets || null;
        if (!widgets) return;

        sceneCtx.widgetPanelStyle = window.SkySceneWidgetUtils.panelStyle(sceneCtx);

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
