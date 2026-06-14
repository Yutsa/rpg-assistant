(ns rpg-assistant-web.views
  (:require [rpg-assistant-web.views.campaign-documents :as campaign-documents]
            [rpg-assistant-web.views.campaigns :as campaigns]
            [rpg-assistant-web.views.document-explorer :as document-explorer]
            [rpg-assistant-web.views.placeholder :as placeholder]
            [rpg-assistant-web.views.shell :as shell]
            [rpg-assistant-web.views.stat-block-detail :as stat-block-detail]
            [rpg-assistant-web.views.stat-blocks :as stat-blocks]))

(defn page-view [state]
  (let [location (:location state)
        params (:location/params location {})
        body (case (:location/page-id location)
               :pages/campaigns
               (campaigns/campaigns-view state)

               :pages/campaign-documents
               (campaign-documents/campaign-documents-view state (:campaign-id params))

               (:pages/document-explorer :pages/document-chunk)
               (document-explorer/document-explorer-view state location)

               :pages/stat-blocks
               (stat-blocks/stat-blocks-view state (:document-id params))

               :pages/stat-block-detail
               (stat-block-detail/stat-block-detail-view
                state (:document-id params) (:stat-block-name params))

               (placeholder/placeholder-view
                "Page introuvable"
                "Cette URL ne correspond à aucune vue."))]
    (shell/shell-view location body)))

(defn render [state]
  (page-view state))
