(ns rpg-assistant-web.views.chunk-list)

(defn chunk-list-view [document-id chunks & [{:keys [selected-chunk-id]}]]
  (if (empty? chunks)
    [:p.muted {:style {:padding "1rem"}} "Aucun chunk pour cette section."]
    [:ul.chunk-list
     (for [chunk chunks]
       [:li.chunk-item {:key (:id chunk)}
        [:ui/a {:ui/location {:location/page-id :pages/document-chunk
                               :location/params {:document-id document-id
                                                  :chunk-id (:id chunk)}}
                :class (when (= selected-chunk-id (:id chunk)) "active")}
         [:div.chunk-meta
          [:span (str "p." (:page_start chunk)
                      (when (not= (:page_end chunk) (:page_start chunk))
                        (str "–" (:page_end chunk))))]
          (when-let [ct (:chunk_type chunk)]
            [:span.badge ct])
          (when (= (:chunk_type_hint chunk) "stat_block")
            [:span.badge.stat "stat_block"])
          [:span (str (:token_count chunk) " tokens")]]
         [:div (or (:text_preview chunk) "…")]]])]))
