from django.contrib import admin
from .models import Page, Argument, ArgumentComment, Prompt, TextInput, TextBlock, AIModel

# Register your models here.
@admin.register(AIModel)
class AIModelAdmin(admin.ModelAdmin):
    list_display = ('name', 'provider', 'model_name', 'is_active')
    list_filter = ('provider', 'is_active')

class TextBlockInline(admin.TabularInline):
    model = TextBlock
    extra = 0

class ArgumentInline(admin.TabularInline):
    model = Argument
    extra = 0

@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ('url', 'created_at', 'updated_at')
    search_fields = ('url',)
    inlines = [TextBlockInline, ArgumentInline]

@admin.register(TextBlock)
class TextBlockAdmin(admin.ModelAdmin):
    list_display = ('page', 'selector', 'start_offset', 'end_offset')
    list_filter = ('page',)

@admin.register(Argument)
class ArgumentAdmin(admin.ModelAdmin):
    list_display = ('summary', 'stance', 'page', 'user_edited', 'created_at')
    list_filter = ('stance', 'user_edited', 'page')
    search_fields = ('summary', 'text_original')

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
