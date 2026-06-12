(ns rpg-assistant.web.utils.bbox)

(defn bbox-to-viewport
  [bbox page-width-pts image-width-px]
  (let [scale (/ image-width-px page-width-pts)
        x0 (.-x0 bbox)
        y0 (.-y0 bbox)
        x1 (.-x1 bbox)
        y1 (.-y1 bbox)]
    #js {:left (* x0 scale)
         :top (* y0 scale)
         :width (* (- x1 x0) scale)
         :height (* (- y1 y0) scale)}))
