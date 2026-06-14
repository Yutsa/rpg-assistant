(ns rpg-assistant-web.views.campaign-documents
  (:require [rpg-assistant-web.views.common :as common]))

(defn campaign-documents-view [state campaign-id]
  (let [{:keys [documents summary loading? error]}
        (get-in state [:documents-by-campaign campaign-id]
                {:documents nil :summary nil :loading? true :error nil})]
    (cond
      loading? (common/loading-view)

      error
      (common/error-view error :on-retry :load-campaign-documents)

      (empty? documents)
      (common/empty-state-view
       (str "Aucun document pour " campaign-id)
       [:p.muted "Importez un PDF avec la CLI pour cette campagne."])

      :else
      [:main.page
       [:h2 (str "Documents — " campaign-id)]
       (when summary
         [:p.muted
          (str (:section_count summary) " sections · "
               (:chunk_count summary) " chunks · "
               (:entities summary) " entités")])
       [:div.card-grid
        (for [doc documents]
          [:ui/a.card {:key (:id doc)
                       :ui/location {:location/page-id :pages/document-explorer
                                     :location/params {:document-id (:id doc)}}}
           [:h3 (:filename doc)]
           [:p.muted
            (str (:page_count doc) " pages · "
                 (:section_count doc) " sections · "
                 (:chunk_count doc) " chunks")]
           (when-let [status (:latest_ingestion_status doc)]
             [:p.muted (str "Import raw : " status)])])]])))
