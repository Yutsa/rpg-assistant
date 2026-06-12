(ns rpg-assistant.web.components.pdf-source-panel
  (:require [uix.core :as uix :refer [defui $]]
            [rpg-assistant.web.api :as api]
            [rpg-assistant.web.components.bbox-overlay :refer [bbox-overlay]]
            [rpg-assistant.web.hooks :refer [use-pdf-path]]))

(defn- load-page-data!
  [document-id page set-meta! set-blocks! set-error! set-loading! set-needs-override!]
  (set-loading! true)
  (set-error! nil)
  (-> (js/Promise.all
       #js [(api/api-fetch (str "/documents/" document-id "/pages/" page))
            (api/api-fetch (str "/documents/" document-id "/pages/" page "/blocks"))])
      (.then (fn [results]
               (set-meta! (aget results 0))
               (set-blocks! (aget results 1))
               (set-loading! false)))
      (.catch (fn [err]
                (if (and (= (api/error-status err) 404)
                         (= (.-code (api/error-body err)) "pdf_not_found"))
                  (do
                    (set-needs-override! true)
                    (set-error! (.-message err)))
                  (set-error! (if (instance? js/Error err)
                                (.-message err)
                                "Erreur de chargement")))
                (set-loading! false)))))

(defui pdf-page-image
  [{:keys [render-src page blocks highlight meta
           image-width set-image-width! image-height set-image-height!
           set-needs-override! set-error!]}]
  ($ :div {:style #js {:position "relative" :display "inline-block"}}
    ($ :img {:key render-src
             :src render-src
             :alt (str "Page " page)
             :on-load (fn [e]
                        (let [img (.-target e)]
                          (set-image-width! (.-clientWidth img))
                          (set-image-height! (.-clientHeight img))))
             :on-error (fn [_]
                         (set-needs-override! true)
                         (set-error!
                          "Impossible de charger l'image PDF. Indiquez le chemin absolu du fichier source."))})
    (when (pos? image-width)
      ($ bbox-overlay {:blocks blocks
                       :highlight highlight
                       :page-width-pts (.-width meta)
                       :image-width-px image-width
                       :image-height-px image-height}))))

(defui pdf-source-panel
  [{:keys [document-id page highlight on-close]}]
  (let [{:keys [pdfPath needsOverride setNeedsOverride draftPath setDraftPath saveDraft clearPath]}
        (use-pdf-path document-id)
        [meta set-meta!] (uix/use-state nil)
        [blocks set-blocks!] (uix/use-state #js [])
        [image-width set-image-width!] (uix/use-state 0)
        [image-height set-image-height!] (uix/use-state 0)
        [error set-error!] (uix/use-state nil)
        [loading set-loading!] (uix/use-state true)
        render-src (api/page-render-url document-id page {:dpi 150 :pdf-path pdfPath})
        load-meta (uix/use-callback
                   #(load-page-data! document-id page set-meta! set-blocks! set-error! set-loading! setNeedsOverride)
                   [document-id page setNeedsOverride])]
    (uix/use-effect
      (fn []
        (load-meta)
        js/undefined)
      [load-meta])
    ($ :div.pdf-panel
      ($ :div.pdf-toolbar
        ($ :strong (str "Source PDF — page " page))
        (when on-close
          ($ :button.btn {:type "button" :on-click on-close} "Fermer")))
      (when (or needsOverride error)
        ($ :div.pdf-banner
          ($ :p (or error
                    "PDF introuvable sur ce poste. Collez le chemin absolu du fichier (réimport CLI si déplacé)."))
          ($ :input {:type "text"
                     :placeholder "/chemin/vers/aventure.pdf"
                     :value draftPath
                     :on-change #(setDraftPath (.. % -target -value))})
          ($ :div {:style #js {:display "flex" :gap "0.5rem" :marginTop "0.5rem"}}
            ($ :button.btn.primary {:type "button" :on-click saveDraft} "Enregistrer le chemin")
            (when pdfPath
              ($ :button.btn {:type "button" :on-click clearPath} "Effacer")))))
      ($ :div.pdf-viewport
        (when loading ($ :p.muted "Chargement de la page…"))
        (when (and (not loading) meta)
          ($ pdf-page-image {:render-src render-src
                             :page page
                             :blocks blocks
                             :highlight highlight
                             :meta meta
                             :image-width image-width
                             :set-image-width! set-image-width!
                             :image-height image-height
                             :set-image-height! set-image-height!
                             :set-needs-override! setNeedsOverride
                             :set-error! set-error!}))))))
