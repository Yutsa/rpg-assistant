(ns rpg-assistant-web.state
  (:require [rpg-assistant-web.router :as router]))

(def initial-pdf-panel
  {:open false :page nil :highlight nil :mobile-open? false})

(defonce store
  (atom {:location (router/current-location)

         :campaigns nil
         :campaigns-loading? false
         :campaigns-error nil

         :documents-by-campaign {}
         :explorer-by-document {}
         :stat-blocks-by-document {}
         :stat-block-detail-by-key {}
         :stat-block-filter ""

         :pdf-panel initial-pdf-panel
         :mobile-tab :content

         :pdf-by-document {}}))

(defn explorer-state [state document-id]
  (get-in state [:explorer-by-document document-id]
          {:sections nil :chunks nil :chunk nil
           :loading? false :error nil}))

(defn documents-state [state campaign-id]
  (get-in state [:documents-by-campaign campaign-id]
          {:documents nil :summary nil :loading? false :error nil}))

(defn stat-blocks-state [state document-id]
  (get-in state [:stat-blocks-by-document document-id]
          {:entries nil :loading? false :error nil}))

(defn stat-block-detail-state [state document-id name]
  (get-in state [:stat-block-detail-by-key [document-id name]]
          {:detail nil :candidates nil :loading? false :error nil}))

(defn pdf-state [state document-id]
  (get-in state [:pdf-by-document document-id]
          {:meta nil :blocks nil :image-width 0 :image-height 0
           :needs-override? false :draft-path "" :error nil :loading? false}))
