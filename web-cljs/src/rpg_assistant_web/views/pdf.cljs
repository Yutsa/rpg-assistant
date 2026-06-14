(ns rpg-assistant-web.views.pdf
  (:require [clojure.string :as str]
            [rpg-assistant-web.api :as api]
            [rpg-assistant-web.events :as events]
            [rpg-assistant-web.utils.bbox :as bbox]
            [rpg-assistant-web.utils.pdf-path :as pdf-path]))

(defn- overlay-rects [blocks highlight page-width-pts image-width-px]
  (let [highlight-ids (set (:page-block-ids highlight []))]
    (concat
     (for [block blocks]
       {:key (:id block)
        :rect (bbox/bbox->viewport (:bbox block) page-width-pts image-width-px)
        :highlighted (contains? highlight-ids (:id block))
        :label (subs (:text block) 0 (min 80 (count (:text block))))})
     (map-indexed
      (fn [idx bbox-item]
        {:key (str "fallback-" idx)
         :rect (bbox/bbox->viewport bbox-item page-width-pts image-width-px)
         :highlighted true
         :label nil})
      (:bbox-fallbacks highlight [])))))

(defn- bbox-overlay [blocks highlight page-width-pts image-width-px image-height-px]
  (let [rects (overlay-rects blocks highlight page-width-pts image-width-px)]
    [:svg.pdf-overlay
     {:width image-width-px
      :height image-height-px
      :aria-hidden true}
     (for [{:keys [key rect highlighted label]} rects]
       [:rect {:key key
               :class (str/join " "
                                (remove nil?
                                        [(when highlighted "source-highlight")
                                         (when label "hoverable")]))
               :x (:left rect)
               :y (:top rect)
               :width (:width rect)
               :height (:height rect)
               :stroke-width 1}
        (when label [:title label])])]))

(defn pdf-source-panel
  [document-id page highlight pdf-state & [{:keys [on-close?]}]]
  (let [{:keys [meta blocks image-width image-height needs-override?
                draft-path error loading?]} pdf-state
        stored-path (pdf-path/load-path document-id)
        render-src (api/page-render-url document-id page
                                        {:dpi 150
                                         :pdf-path (or stored-path nil)})]
    [:div.pdf-panel
     [:div.pdf-toolbar
      [:strong (str "Source PDF — page " page)]
      (when on-close?
        [:button.btn {:on {:click [[:close-pdf-panel]]}} "Fermer"])]

     (when (or needs-override? error)
       [:div.pdf-banner
        [:p (or error
                "PDF introuvable sur ce poste. Collez le chemin absolu du fichier (réimport CLI si déplacé).")]
        [:input {:type "text"
                 :placeholder "/chemin/vers/aventure.pdf"
                 :value (or draft-path "")
                 :on {:input [[:set-pdf-draft-path :event/target.value]]}}]
        [:div {:style {:display "flex" :gap "0.5rem" :margin-top "0.5rem"}}
         [:button.btn.primary {:on {:click [[:save-pdf-path]]}}
          "Enregistrer le chemin"]
         (when stored-path
           [:button.btn {:on {:click [[:clear-pdf-path]]}} "Effacer"])]])

     [:div.pdf-viewport
      (when loading?
        [:p.muted "Chargement de la page…"])
      (when (and (not loading?) meta)
        [:div {:style {:position "relative" :display "inline-block"}}
         [:img {:key render-src
                :src render-src
                :alt (str "Page " page)
                :on {:load (fn [e]
                             (let [img (.-target e)]
                               (events/pdf-image-loaded! (.-clientWidth img) (.-clientHeight img))))
                     :error (fn [_e] (events/pdf-image-error!))}}]
         (when (pos? image-width)
           (bbox-overlay blocks highlight (:width meta) image-width image-height))])]]))
