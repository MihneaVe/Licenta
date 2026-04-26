from django.contrib import admin
from .models import YourModelName  # Replace with your actual model name

@admin.register(YourModelName)  # Replace with your actual model name
class YourModelAdmin(admin.ModelAdmin):  # Replace with your actual model admin class name
    list_display = ('field1', 'field2', 'field3')  # Replace with your actual fields
    search_fields = ('field1', 'field2')  # Replace with your actual fields
    list_filter = ('field3',)  # Replace with your actual fields

# Register any additional models here
# admin.site.register(AnotherModel, AnotherModelAdmin)  # Example for another model admin registration