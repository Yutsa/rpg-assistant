(ns rpg-assistant-web.views.chunk-reader
  (:require [clojure.string :as str]))

(defn- first-source-page [chunk]
  (if-let [spans (:source_spans chunk)]
    (if (seq spans)
      (:page (first spans))
      (:page_start chunk))
    (:page_start chunk)))

(defn- highlight-from-chunk [chunk]
  (let [spans (:source_spans chunk [])]
    {:page-block-ids (vec (mapcat :page_block_ids spans))
     :bbox-fallbacks (vec (remove nil? (map :bbox spans)))}))

(defn- stat-name-from-chunk [chunk]
  (when (= (:chunk_type_hint chunk) "stat_block")
    (get-in chunk [:metadata :stat_block :name])))

(defn chunk-reader-view [chunk]
  (let [stat-name (stat-name-from-chunk chunk)]
    [:article.chunk-reader
     [:div.chunk-meta
      [:span.badge (or (:chunk_type chunk) (:chunk_type_hint chunk) "chunk")]
      [:span (str "p." (:page_start chunk)
                  (when (not= (:page_end chunk) (:page_start chunk))
                    (str "–" (:page_end chunk))))]
      [:span (str (:token_count chunk) " tokens")]
      (when (:needs_rechunk chunk)
        [:span.badge "needs_rechunk"])]

     [:div.chunk-actions
      [:button.btn.primary
       {:on {:click [[:show-pdf-source (first-source-page chunk)
                      (highlight-from-chunk chunk)]]}}
       "Voir la source"]
      (when stat-name
        [:ui/a.btn
         {:ui/location {:location/page-id :pages/stat-block-detail
                        :location/params {:document-id (:document_id chunk)
                                           :stat-block-name stat-name}}}
         (str "Fiche " stat-name)])]

     [:pre (:text chunk)]

     [:details {:style {:margin-top "1rem"}}
      [:summary.muted "Métadonnées"]
      [:pre {:style {:font-size "0.85rem"}}
       (js/JSON.stringify
        (clj->js {:source_spans (:source_spans chunk)
                  :metadata (:metadata chunk)})
        nil 2)]]]))
