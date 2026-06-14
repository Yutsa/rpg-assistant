(ns rpg-assistant-web.views.stat-block-detail
  (:require [rpg-assistant-web.state :as state]
            [rpg-assistant-web.views.common :as common]
            [rpg-assistant-web.views.pdf :as pdf]))

(defn- stat-block-detail-content [detail]
  (let [first-ref (first (:source_refs detail))]
    [:article.chunk-reader
     [:header
      [:h2 {:style {:margin-top 0}} (:name detail)]
      (when-let [subtitle (:subtitle detail)]
        [:p.muted subtitle])
      (when-let [nc (:nc detail)]
        [:p (str "NC " nc)])]

     (when-let [attrs (:attributes detail)]
       (when (seq attrs)
         [:div.stat-block-section
          [:h3 "Attributs"]
          [:table.stat-table
           [:tbody
            (for [[k v] attrs]
              [:tr {:key (name k)}
               [:th (name k)]
               [:td (str v)]])]]]))

     (when-let [abilities (:abilities detail)]
       (when (seq abilities)
         [:div.stat-block-section
          [:h3 "Capacités"]
          [:ul
           (for [ability abilities]
             (let [title (if (string? ability) ability (:title ability))
                   text (when (map? ability) (:text ability))]
               [:li {:key title}
                [:strong title]
                (when text
                  [:p {:style {:margin "0.35rem 0 0" :white-space "pre-wrap"}} text])]))]]))

     (when first-ref
       [:div.chunk-actions
        [:button.btn.primary
         {:on {:click [[:show-pdf-source
                        (:page first-ref)
                        {:page-block-ids (:page_block_ids first-ref)
                         :bbox-fallbacks (if-let [b (:bbox first-ref)] [b] [])}]]}}
         "Voir la source"]])]))

(defn- detail-layout [detail document-id page highlight pdf-visible pdf-state]
  [:div.explorer-layout {:style {:min-height "60vh"}}
   [:section.explorer-column {:style {:border-right "1px solid var(--border)"}}
    (stat-block-detail-content detail)]
   (when pdf-visible
     [:aside.explorer-column
      (pdf/pdf-source-panel document-id page highlight pdf-state)])])

(defn stat-block-detail-view [state document-id name]
  (let [{:keys [detail candidates loading? error]}
        (state/stat-block-detail-state state document-id name)
        {:keys [open page highlight]} (:pdf-panel state)
        pdf-visible (and open (some? page))
        pdf-state (state/pdf-state state document-id)]
    (cond
      loading? (common/loading-view)

      (seq candidates)
      [:main.page
       [:div.state-box
        [:p error]
        [:ul
         (for [candidate candidates]
           [:li {:key (:chunk_id candidate)}
            [:ui/a
             {:ui/location {:location/page-id :pages/stat-block-detail
                            :location/params {:document-id document-id
                                               :stat-block-name (:name candidate)}}}
             (str (:name candidate)
                  " (NC " (or (:nc candidate) "—")
                  ", p." (:start (:pages candidate)) ")")]])]]]

      (or error (nil? detail))
      (common/error-view (or error "Fiche introuvable"))

      :else
      (detail-layout detail document-id page highlight pdf-visible pdf-state))))
