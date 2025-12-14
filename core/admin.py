from django.contrib import admin
from .models import Page, Argument, ArgumentComment, Prompt, TextInput, TextBlock, AIModel, Theme, Reformulation

# Register your models here.
@admin.register(AIModel)
class AIModelAdmin(admin.ModelAdmin):
    list_display = ('name', 'provider', 'model_name', 'is_active')
    list_filter = ('provider', 'is_active')

@admin.register(Theme)
class ThemeAdmin(admin.ModelAdmin):
    list_display = ('name',)

class TextBlockInline(admin.TabularInline):
    model = TextBlock
    extra = 0
    fields = ('selector', 'hypostasis', 'modes', 'significant_extract', 'text')
    show_change_link = True

class ArgumentInline(admin.TabularInline):
    model = Argument
    extra = 0
    fk_name = 'page'

class ReformulationInline(admin.TabularInline):
    model = Reformulation
    extra = 0

class ArgumentBlockInline(admin.StackedInline):
    model = Argument
    extra = 0
    fk_name = 'text_block'
    verbose_name = "Argument lié au bloc"
    verbose_name_plural = "Arguments liés au bloc"

@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ('url', 'status', 'created_at', 'updated_at')
    search_fields = ('url', 'title')
    list_filter = ('status',)
    inlines = [TextBlockInline, ArgumentInline]

@admin.register(TextBlock)
class TextBlockAdmin(admin.ModelAdmin):
    list_display = ('page', 'selector', 'hypostasis', 'modes', 'start_offset', 'end_offset')
    list_filter = ('page', 'hypostasis', 'modes', 'themes')
    search_fields = ('text', 'significant_extract')
    filter_horizontal = ('themes',)
    inlines = [ArgumentBlockInline, ReformulationInline]
    
    fieldsets = (
        ('Ancrage', {
            'fields': ('page', 'selector', 'start_offset', 'end_offset')
        }),
        ('Contenu', {
            'fields': ('text', 'significant_extract')
        }),
        ('Analyse', {
            'fields': ('hypostasis', 'modes', 'themes')
        }),
    )

@admin.register(Argument)
class ArgumentAdmin(admin.ModelAdmin):
    list_display = ('summary', 'page', 'text_block', 'user_edited', 'created_at')
    list_filter = ('user_edited', 'page')
    search_fields = ('summary', 'text_original')
    autocomplete_fields = ['page', 'text_block']

@admin.register(ArgumentComment)
class ArgumentCommentAdmin(admin.ModelAdmin):
    list_display = ('author', 'argument', 'created_at')

class TextInputInline(admin.TabularInline):
    model = TextInput
    extra = 1

@admin.register(Prompt)
class PromptAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    inlines = [TextInputInline]

@admin.register(TextInput)
class TextInputAdmin(admin.ModelAdmin):
    list_display = ('name', 'prompt', 'role', 'order')
    list_filter = ('prompt', 'role')
    ordering = ('prompt', 'order')
