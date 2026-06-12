(ns rpg-assistant-web.views
  (:require [rpg-assistant-web.views.campaigns :as campaigns]
            [rpg-assistant-web.views.placeholder :as placeholder]
            [rpg-assistant-web.views.shell :as shell]))

(defn page-view [state]
  (let [location (:location state)
        params (:location/params location {})
        body (case (:location/page-id location)
               :pages/campaigns (campaigns/campaigns-view state)

               :pages/campaign-documents
               (placeholder/placeholder-view
                (str "Documents — " (:campaign-id params))
                "Sélection de document à implémenter.")

               (:pages/document-explorer :pages/document-chunk)
               (placeholder/placeholder-view
                (str "Exploration — " (:document-id params))
                "Arbre de sections, chunks et panneau PDF à implémenter.")

               :pages/stat-blocks
               (placeholder/placeholder-view
                (str "Fiches stats — " (:document-id params))
                "Index des fiches COF2 à implémenter.")

               :pages/stat-block-detail
               (placeholder/placeholder-view
                (:stat-block-name params)
                (str "Document " (:document-id params)))

               (placeholder/placeholder-view
                "Page introuvable"
                "Cette URL ne correspond à aucune vue."))]
    (shell/shell-view location body)))

(defn render [state]
  (page-view state))
