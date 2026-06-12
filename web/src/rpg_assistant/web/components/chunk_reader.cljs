(ns rpg-assistant.web.components.chunk-reader
  (:require ["react-router-dom" :refer [Link]]
            [re-frame.core :as rf]
            [uix.core :refer [defui $]]))

(defn- first-source-page [^js chunk]
  (if (pos? (.-length (.-source_spans chunk)))
    (.-page (aget (.-source_spans chunk) 0))
    (.-page_start chunk)))

(defn- highlight-from-chunk [^js chunk]
  (let [spans (.-source_spans chunk)
        page-block-ids (reduce (fn [acc ^js span]
                                 (into acc (js->clj (.-page_block_ids span))))
                               []
                               spans)
        bbox-fallbacks (reduce (fn [acc ^js span]
                                 (if-let [bbox (.-bbox span)]
                                   (conj acc bbox)
                                   acc))
                               []
                               spans)]
    #js {:pageBlockIds (clj->js page-block-ids)
         :bboxFallbacks (clj->js bbox-fallbacks)}))

(defui chunk-reader
  [{:keys [chunk document-id]}]
  (let [stat-name (when (= (.-chunk_type_hint chunk) "stat_block")
                    (when-let [metadata (.-metadata chunk)]
                      (when-let [sb (or (.-stat_block metadata) (aget metadata "stat_block"))]
                        (or (.-name sb) (aget sb "name")))))
        page-end (.-page_end chunk)
        page-start (.-page_start chunk)]
    ($ :article.chunk-reader
      ($ :div.chunk-meta
        ($ :span.badge (or (.-chunk_type chunk) (.-chunk_type_hint chunk) "chunk"))
        ($ :span (str "p." page-start
                      (when (not= page-end page-start)
                        (str "–" page-end))))
        ($ :span (str (.-token_count chunk) " tokens"))
        (when (.-needs_rechunk chunk)
          ($ :span.badge "needs_rechunk")))
      ($ :div.chunk-actions
        ($ :button.btn.primary
          {:type "button"
           :on-click #(rf/dispatch [:pdf/show-source
                                    (first-source-page chunk)
                                    (highlight-from-chunk chunk)])}
          "Voir la source")
        (when stat-name
          ($ Link {:class "btn"
                   :to (str "/documents/" document-id
                            "/stat-blocks/" (js/encodeURIComponent stat-name))}
            (str "Fiche " stat-name))))
      ($ :pre (.-text chunk))
      ($ :details {:style #js {:marginTop "1rem"}}
        ($ :summary.muted "Métadonnées")
        ($ :pre {:style #js {:fontSize "0.85rem"}}
          (js/JSON.stringify
           #js {:source_spans (.-source_spans chunk)
                :metadata (.-metadata chunk)}
           nil
           2))))))
