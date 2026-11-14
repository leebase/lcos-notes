/* Caller-owned observer: read mapped GTK widgets; never invoke app callbacks. */
#include <gtk/gtk.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static FILE *out;
static GtkWidget *top;
static const char *title;
static void field(const char *s) {
    gchar *b=g_base64_encode((const guchar *)(s?s:""),s?strlen(s):0);
    fprintf(out,"\t%s",b);g_free(b);
}
static void rows(GtkTreeView *view,GtkTreeModel *model,GtkTreeIter *it) {
    do {
        fprintf(out,"R");field(title);
        GtkTreePath *p=gtk_tree_model_get_path(model,it);
        char *s=gtk_tree_path_to_string(p);field(s);g_free(s);gtk_tree_path_free(p);
        for(int i=0;i<gtk_tree_model_get_n_columns(model);++i)
            if(gtk_tree_model_get_column_type(model,i)==G_TYPE_STRING) {
                gchar *v=NULL;gtk_tree_model_get(model,it,i,&v,-1);field(v);g_free(v);
            }
        fputc('\n',out);
        GtkTreeIter child;if(gtk_tree_model_iter_children(model,&child,it))rows(view,model,&child);
    }while(gtk_tree_model_iter_next(model,it));
}
static void walk(GtkWidget *w) {
    if(!gtk_widget_get_visible(w)||!gtk_widget_get_mapped(w))return;
    int x=0,y=0,ox=0,oy=0;GtkAllocation a;gtk_widget_get_allocation(w,&a);
    gtk_widget_translate_coordinates(w,top,0,0,&x,&y);
    if(gtk_widget_get_window(top))gdk_window_get_origin(gtk_widget_get_window(top),&ox,&oy);
    fprintf(out,"W");field(title);field(G_OBJECT_TYPE_NAME(w));
    fprintf(out,"\t%d\t%d\t%d\t%d",x+ox,y+oy,a.width,a.height);
    char *owned=NULL;const char *text="";
    if(GTK_IS_LABEL(w))text=gtk_label_get_text(GTK_LABEL(w));
    else if(GTK_IS_ENTRY(w))text=gtk_entry_get_text(GTK_ENTRY(w));
    else if(GTK_IS_MENU_ITEM(w))text=gtk_menu_item_get_label(GTK_MENU_ITEM(w));
    else if(GTK_IS_BUTTON(w))text=gtk_button_get_label(GTK_BUTTON(w));
    else if(GTK_IS_TEXT_VIEW(w)){
        GtkTextBuffer *b=gtk_text_view_get_buffer(GTK_TEXT_VIEW(w));GtkTextIter s,e;
        gtk_text_buffer_get_bounds(b,&s,&e);owned=gtk_text_buffer_get_text(b,&s,&e,FALSE);text=owned;
    }
    field(text);fputc('\n',out);g_free(owned);
    if(GTK_IS_TREE_VIEW(w)){
        GtkTreeModel *m=gtk_tree_view_get_model(GTK_TREE_VIEW(w));GtkTreeIter it;
        if(m&&gtk_tree_model_get_iter_first(m,&it))rows(GTK_TREE_VIEW(w),m,&it);
    }
    if(GTK_IS_CONTAINER(w)){
        GList *children=gtk_container_get_children(GTK_CONTAINER(w));
        for(GList *i=children;i;i=i->next)walk(GTK_WIDGET(i->data));g_list_free(children);
    }
}
static gboolean observe(gpointer unused){
    (void)unused;const char *p=getenv("VAULT_INSPECT_FILE");if(!p)return G_SOURCE_CONTINUE;
    char *tmp=g_strconcat(p,".tmp",NULL);out=fopen(tmp,"w");if(!out){g_free(tmp);return G_SOURCE_CONTINUE;}
    GList *windows=gtk_window_list_toplevels();for(GList *i=windows;i;i=i->next){
        top=GTK_WIDGET(i->data);title=gtk_window_get_title(GTK_WINDOW(top));walk(top);
    }
    g_list_free(windows);fclose(out);rename(tmp,p);g_free(tmp);return G_SOURCE_CONTINUE;
}
__attribute__((constructor))static void start(void){if(getenv("VAULT_INSPECT_FILE"))g_timeout_add(100,observe,NULL);}
