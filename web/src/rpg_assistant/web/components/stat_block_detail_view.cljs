(ns rpg-assistant.web.components.stat-block-detail-view
  (:require [re-frame.core :as rf]
            [uix.core :refer [defui $]]))

(defui stat-block-detail-view
  [{:keys [detail]}]
  (let [source-refs (or (aget detail "source_refs") #js [])
        first-ref (when (pos? (.-length source-refs))
                    (aget source-refs 0))
        attrs (or (aget detail "attributes") (.-attributes detail))
        abilities (or (aget detail "abilities") (.-abilities detail))]
    ($ :article.chunk-reader
      ($ :header
        ($ :h2 {:style #js {:marginTop 0}} (.-name detail))
        (when-let [sub (.-subtitle detail)]
          ($ :p.muted sub))
        (when (some? (.-nc detail))
          ($ :p (str "NC " (.-nc detail)))))
      (when (and attrs (pos? (.-length (js/Object.keys attrs))))
        ($ :div
          ($ :h3 "Attributs")
          ($ :table.stat-table
            ($ :tbody
              (for [^js key (js/Object.keys attrs)]
                ($ :tr {:key key}
                  ($ :th key)
                  ($ :td (aget attrs key))))))))
      (when (and abilities (pos? (.-length abilities)))
        ($ :div
          ($ :h3 "Capacités")
          ($ :ul
            (for [^js ab (array-seq abilities)]
              ($ :li {:key (aget ab "title")}
                ($ :strong (aget ab "title"))
                (when-let [text (aget ab "text")]
                  ($ :p {:style #js {:margin "0.35rem 0 0" :whiteSpace "pre-wrap"}}
                    text)))))))
      (when first-ref
        ($ :div.chunk-actions
          ($ :button.btn.primary
            {:type "button"
             :on-click #(rf/dispatch
                          [:pdf/show-source
                           (aget first-ref "page")
                           #js {:pageBlockIds (aget first-ref "page_block_ids")
                                :bboxFallbacks (if-let [bbox (aget first-ref "bbox")]
                                                 #js [bbox]
                                                 #js [])}])}
            "Voir la source"))))))
