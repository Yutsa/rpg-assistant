(ns rpg-assistant.web.components.bbox-overlay
  (:require [uix.core :as uix :refer [defui $]]
            [rpg-assistant.web.utils.bbox :refer [bbox-to-viewport]]))

(defn- rects-from-highlight
  [blocks highlight page-width-pts image-width-px]
  (let [highlight-ids (set (when highlight (js->clj (.-pageBlockIds highlight))))
        rects (atom [])]
    (doseq [^js block blocks]
      (let [highlighted (contains? highlight-ids (.-id block))]
        (swap! rects conj
               {:key (.-id block)
                :rect (bbox-to-viewport (.-bbox block) page-width-pts image-width-px)
                :highlighted highlighted
                :label (subs (.-text block) 0 (min 80 (.-length (.-text block))))})))
    (when-let [fallbacks (and highlight (.-bboxFallbacks highlight))]
      (doseq [[idx bbox] (map-indexed vector (js->clj fallbacks))]
        (swap! rects conj
               {:key (str "fallback-" idx)
                :rect (bbox-to-viewport (clj->js bbox) page-width-pts image-width-px)
                :highlighted true})))
    @rects))

(defui bbox-overlay
  [{:keys [blocks highlight page-width-pts image-width-px image-height-px]}]
  (let [[hovered set-hovered!] (uix/use-state nil)
        rects (uix/use-memo
               #(rects-from-highlight blocks highlight page-width-pts image-width-px)
               [blocks highlight page-width-pts image-width-px])]
    ($ :svg.pdf-overlay
      {:width image-width-px
       :height image-height-px
       :aria-hidden true}
      (for [{:keys [key rect highlighted label]} rects]
        ($ :rect {:key key
                   :class (clojure.string/join " "
                                               (remove nil?
                                                       [(when highlighted "source-highlight")
                                                        (when label "hoverable")]))
                   :x (.-left rect)
                   :y (.-top rect)
                   :width (.-width rect)
                   :height (.-height rect)
                   :strokeWidth 1
                   :onMouseEnter #(when label (set-hovered! key))
                   :onMouseLeave #(set-hovered! nil)}
          (when (and label (= hovered key))
            ($ :title label)))))))
