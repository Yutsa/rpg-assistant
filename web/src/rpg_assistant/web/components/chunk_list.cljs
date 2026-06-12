(ns rpg-assistant.web.components.chunk-list
  (:require ["react-router-dom" :refer [Link]]
            [uix.core :refer [defui $]]))

(defui chunk-list
  [{:keys [document-id chunks selected-chunk-id]}]
  (if (zero? (.-length chunks))
    ($ :p.muted {:style #js {:padding "1rem"}} "Aucun chunk pour cette section.")
    ($ :ul.chunk-list
      (for [^js chunk chunks]
        (let [page-end (.-page_end chunk)
              page-start (.-page_start chunk)]
          ($ :li.chunk-item {:key (.-id chunk)}
            ($ Link {:to (str "/documents/" document-id "/chunks/" (.-id chunk))
                     :class (when (= selected-chunk-id (.-id chunk)) "active")}
              ($ :div.chunk-meta
                ($ :span (str "p." page-start
                              (when (not= page-end page-start)
                                (str "–" page-end))))
                (when-let [ct (.-chunk_type chunk)]
                  ($ :span.badge ct))
                (when (= (.-chunk_type_hint chunk) "stat_block")
                  ($ :span.badge.stat "stat_block"))
                ($ :span (str (.-token_count chunk) " tokens")))
              ($ :div (or (.-text_preview chunk) "…")))))))))
