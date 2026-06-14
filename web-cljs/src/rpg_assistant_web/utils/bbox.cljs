(ns rpg-assistant-web.utils.bbox)

(defn bbox->viewport
  "Convertit une bbox PDF (points) en rectangle viewport (pixels image)."
  [bbox page-width-pts image-width-px]
  (let [scale (/ image-width-px page-width-pts)]
    {:left (* (:x0 bbox) scale)
     :top (* (:y0 bbox) scale)
     :width (* (- (:x1 bbox) (:x0 bbox)) scale)
     :height (* (- (:y1 bbox) (:y0 bbox)) scale)}))
