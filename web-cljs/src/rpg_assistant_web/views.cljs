(ns rpg-assistant-web.views
  (:require [rpg-assistant-web.views.campaigns :as campaigns]
            [rpg-assistant-web.views.placeholder :as placeholder]
            [rpg-assistant-web.views.shell :as shell]))

(defn page-view [state]
  (let [route (:route state)
        body (case (:page route)
               :campaigns (campaigns/campaigns-view state)
               :campaign-documents
               (placeholder/placeholder-view
                (str "Documents — " (:campaign-id route))
                "Sélection de document à implémenter.")

               :document-explorer
               (placeholder/placeholder-view
                (str "Exploration — " (:document-id route))
                "Arbre de sections, chunks et panneau PDF à implémenter.")

               :stat-blocks
               (placeholder/placeholder-view
                (str "Fiches stats — " (:document-id route))
                "Index des fiches COF2 à implémenter.")

               :stat-block-detail
               (placeholder/placeholder-view
                (:stat-block-name route)
                (str "Document " (:document-id route)))

               :not-found
               (placeholder/placeholder-view
                "Page introuvable"
                "Cette URL ne correspond à aucune vue."))]
    (shell/shell-view route body)))

(defn render [state]
  (page-view state))
